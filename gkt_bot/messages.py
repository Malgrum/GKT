from __future__ import annotations

import discord

from .formatting import generer_tableau_ff14, generer_tableau_warhammer
from .state import tournois
from .views import TournoiView


async def update_message(interaction: discord.Interaction, message_id: int) -> None:
    tournoi = tournois.get(message_id)
    if not tournoi:
        return

    try:
        embed = discord.Embed(title=tournoi["titre"], color=tournoi.get("color", 0x3498DB))
        embed.add_field(name="📍 Lieu", value=tournoi["lieu"], inline=True)
        embed.add_field(name="📅 Date", value=tournoi["date"], inline=True)
        if tournoi.get("heure"):
            embed.add_field(name="⏰ Heure", value=tournoi["heure"], inline=True)

        max_display = "∞" if tournoi["max_joueurs"] is None else str(tournoi["max_joueurs"])
        embed.add_field(name="👥 Inscrits", value=f"{len(tournoi['inscrits'])}/{max_display}", inline=False)

        if tournoi.get("type") == "warhammer":
            embed.add_field(name="⚔️ Répartition par jeu", value=generer_tableau_warhammer(tournoi), inline=False)
        elif tournoi.get("type") == "ff14":
            embed.add_field(name="🎮 Répartition par rôle", value=generer_tableau_ff14(tournoi), inline=False)
        else:
            embed.add_field(name="✅ Joueurs", value="\n".join(tournoi["inscrits"]) or "Aucun", inline=False)

        if tournoi["attente"]:
            embed.add_field(name="⏳ Liste d'attente", value="\n".join(tournoi["attente"]), inline=False)

        message = await interaction.channel.fetch_message(message_id)
        await message.edit(embed=embed, view=TournoiView(message_id))

    except discord.NotFound:
        print(f"❌ Message {message_id} introuvable")
    except Exception as error:
        print(f"❌ Erreur update_message: {error}")
