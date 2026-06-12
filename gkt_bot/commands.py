from __future__ import annotations

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import tasks

from .formatting import build_registered_mentions, event_has_explicit_time, parse_event_datetime
from .state import bot, tournois
from .storage import charger_tournois, sauvegarder_tournois
from .views import TournoiView


async def _resolve_event_channel(message_id: int, tournoi: dict) -> discord.TextChannel | None:
    channel_id = tournoi.get("channel_id")
    if channel_id:
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel

        try:
            fetched = await bot.fetch_channel(channel_id)
            if isinstance(fetched, discord.TextChannel):
                return fetched
        except Exception:
            pass

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.fetch_message(message_id)
                tournoi["channel_id"] = channel.id
                return channel
            except (discord.NotFound, discord.Forbidden):
                continue
            except Exception:
                continue

    return None


@tasks.loop(minutes=1)
async def verifier_rappels_evenements():
    from datetime import datetime

    now = datetime.now()
    changed = False

    for message_id, tournoi in list(tournois.items()):
        if tournoi.get("rappel_1h_envoye"):
            continue

        date_value = tournoi.get("date")
        heure_value = tournoi.get("heure")

        if not event_has_explicit_time(date_value, heure_value):
            continue

        event_dt = parse_event_datetime(date_value, heure_value)
        if not event_dt:
            continue

        delta_seconds = (event_dt - now).total_seconds()
        if delta_seconds < 0 or delta_seconds > 3600:
            continue

        channel = await _resolve_event_channel(message_id, tournoi)
        if not channel:
            continue

        mentions = build_registered_mentions(tournoi)
        if not mentions:
            tournoi["rappel_1h_envoye"] = True
            changed = True
            continue

        await channel.send(
            f"⏰ **Rappel :** l'événement **{tournoi.get('titre', 'sans titre')}** "
            f"commence dans moins d'1 heure !\nParticipants inscrits : {mentions}"
        )
        tournoi["rappel_1h_envoye"] = True
        changed = True

    if changed:
        sauvegarder_tournois()


@verifier_rappels_evenements.before_loop
async def before_verifier_rappels_evenements():
    await bot.wait_until_ready()


def register_bot_features() -> None:
    @bot.tree.command(name="event", description="Créer un nouvel événement")
    @app_commands.describe(
        template="Type d'événement",
        titre="Nom de l'event",
        lieu="Lieu",
        date="Date",
        max_joueurs="Places max (laisser vide = illimité)",
        heure="Heure (optionnel, ex: 19h ou 19h30)",
    )
    @app_commands.choices(
        template=[
            Choice(name="🏆 Tournoi (Standard / Jeu unique)", value="standard"),
            Choice(name="⚔️ Warhammer (Multiformat)", value="warhammer"),
            Choice(name="🎮 FF14 (Rôles)", value="ff14"),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def creer_tournoi(
        interaction: discord.Interaction,
        template: Choice[str],
        titre: str,
        lieu: str,
        date: str,
        max_joueurs: int = None,
        heure: str = None,
    ):
        if template.value == "standard":
            full_title = f"🏆 {titre}"
            color = 0x3498DB
        elif template.value == "warhammer":
            full_title = f"⚔️ [WARHAMMER] {titre}"
            color = 0x2C3E50
        else:
            full_title = f"🎮 [FF14] {titre}"
            color = 0x6C5CE7

        embed = discord.Embed(title=full_title, color=color)
        embed.add_field(name="📍 Lieu", value=lieu, inline=True)
        embed.add_field(name="📅 Date", value=date, inline=True)
        if heure:
            embed.add_field(name="⏰ Heure", value=heure, inline=True)
        embed.add_field(name="👥 Inscrits", value=f"0/{(max_joueurs or '∞')}", inline=False)

        if template.value == "warhammer":
            embed.add_field(name="⚔️ Répartition par jeu", value="Aucun joueur inscrit", inline=False)
        elif template.value == "ff14":
            embed.add_field(name="🎮 Répartition par rôle", value="Aucun joueur inscrit", inline=False)
        else:
            embed.add_field(name="✅ Joueurs", value="Aucun", inline=False)

        await interaction.response.send_message(
            content="@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )

        message = await interaction.original_response()

        tournois[message.id] = {
            "type": template.value,
            "titre": full_title,
            "lieu": lieu,
            "date": date,
            "heure": heure,
            "channel_id": interaction.channel_id,
            "rappel_1h_envoye": False,
            "max_joueurs": max_joueurs,
            "inscrits": [],
            "attente": [],
            "color": color,
        }

        await message.edit(view=TournoiView(message.id))
        sauvegarder_tournois()

    @bot.event
    async def on_ready():
        charger_tournois()

        for message_id in tournois:
            bot.add_view(TournoiView(message_id))

        if not verifier_rappels_evenements.is_running():
            verifier_rappels_evenements.start()

        await bot.tree.sync()
        print(f"🚀 Bot en ligne : {bot.user}")
        print(f"📊 {len(tournois)} tournois actifs")
