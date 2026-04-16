import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
from discord.app_commands import Choice
import json
import os
import re
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

# --- KEEP ALIVE (évite mise en veille Render) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot Discord en ligne !"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

# --- CONFIGURATION ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

tournois = {}
TOURNOIS_FILE = "tournois.json"


def _extract_user_id_from_entry(entry: str) -> str | None:
    match = re.search(r"<@!?(\d+)>", entry)
    return match.group(1) if match else None


def _user_already_registered(tournoi: dict, user_id: str) -> bool:
    all_participants = tournoi["inscrits"] + tournoi["attente"]
    return any(_extract_user_id_from_entry(entry) == user_id for entry in all_participants)


def _parse_event_datetime(date_value: str | None, heure_value: str | None = None) -> datetime | None:
    if not date_value:
        return None

    text = str(date_value).strip()
    if not text:
        return None

    hour = 0
    minute = 0

    time_match = re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", text, flags=re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        text = text[:time_match.start()] + text[time_match.end():]
    elif heure_value:
        heure_match = re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", str(heure_value), flags=re.IGNORECASE)
        if heure_match:
            hour = int(heure_match.group(1))
            minute = int(heure_match.group(2) or 0)

    parts = re.findall(r"\d+", text)
    if len(parts) < 2:
        return None

    day = int(parts[0])
    month = int(parts[1])
    year = int(parts[2]) if len(parts) >= 3 else datetime.now().year
    if year < 100:
        year += 2000

    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def nettoyer_anciens_evenements() -> None:
    seuil = datetime.now() - timedelta(days=30)
    supprimes = []

    for msg_id, tournoi in list(tournois.items()):
        evenement_dt = _parse_event_datetime(tournoi.get("date"), tournoi.get("heure"))
        if evenement_dt and evenement_dt < seuil:
            del tournois[msg_id]
            supprimes.append(msg_id)

    if supprimes:
        print(f"🧹 {len(supprimes)} événement(s) supprimé(s), passés depuis plus de 30 jours.")
        sauvegarder_tournois()


def _build_registered_mentions(tournoi: dict) -> str:
    mentions = []
    seen = set()

    for entry in tournoi.get("inscrits", []):
        user_id = _extract_user_id_from_entry(entry)
        if user_id and user_id not in seen:
            seen.add(user_id)
            mentions.append(f"<@{user_id}>")

    return " ".join(mentions)


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
    now = datetime.now()
    changed = False

    for message_id, tournoi in list(tournois.items()):
        if tournoi.get("rappel_1h_envoye"):
            continue

        date_value = tournoi.get("date")
        heure_value = tournoi.get("heure")

        has_time_in_date = bool(
            re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", str(date_value), flags=re.IGNORECASE)
        )
        has_time_in_heure = bool(
            heure_value
            and re.search(r"(\d{1,2})\s*(?:h|:)(\d{1,2})?", str(heure_value), flags=re.IGNORECASE)
        )

        # Pas d'heure explicite => pas de rappel automatique.
        if not has_time_in_date and not has_time_in_heure:
            continue

        event_dt = _parse_event_datetime(date_value, heure_value)
        if not event_dt:
            continue

        delta_seconds = (event_dt - now).total_seconds()
        if delta_seconds < 0 or delta_seconds > 3600:
            continue

        channel = await _resolve_event_channel(message_id, tournoi)
        if not channel:
            continue

        mentions = _build_registered_mentions(tournoi)
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

# --- PERSISTANCE ---
def charger_tournois():
    global tournois
    if os.path.exists(TOURNOIS_FILE):
        try:
            if os.path.getsize(TOURNOIS_FILE) == 0:
                tournois = {}
                print("ℹ️ Fichier tournois vide, initialisation d'un état propre.")
                return
            with open(TOURNOIS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tournois = {int(k): v for k, v in data.items()}
                nettoyer_anciens_evenements()
                print(f"✅ {len(tournois)} tournois chargés.")
        except Exception as e:
            tournois = {}
            print(f"❌ Erreur chargement: {e}")

def sauvegarder_tournois():
    try:
        data = {str(k): v for k, v in tournois.items()}
        with open(TOURNOIS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")

# --- FONCTION POUR CRÉER LE TABLEAU WARHAMMER ---
def generer_tableau_warhammer(tournoi):
    """Génère un tableau organisé par jeu pour Warhammer"""
    jeux = {
        "40K": {"emoji": "🚀", "joueurs": []},
        "AOS": {"emoji": "🛡️", "joueurs": []},
        "KT": {"emoji": "🎯", "joueurs": []}
    }
    
    # Répartir les joueurs par jeu
    for entry in tournoi["inscrits"]:
        # Format: @User (40K, AOS) ou @User (KT)
        if "(" in entry and ")" in entry:
            mention = entry.split("(")[0].strip()
            jeux_choisis = entry.split("(")[1].split(")")[0].split(", ")
            for jeu in jeux_choisis:
                if jeu in jeux:
                    jeux[jeu]["joueurs"].append(mention)
    
    # Construire le texte du tableau
    tableau = ""
    for jeu_code, info in jeux.items():
        if info["joueurs"]:
            tableau += f"\n{info['emoji']} **{jeu_code}** ({len(info['joueurs'])} joueur{'s' if len(info['joueurs']) > 1 else ''})\n"
            tableau += "\n".join([f"• {joueur}" for joueur in info["joueurs"]])
            tableau += "\n"
    
    return tableau if tableau else "Aucun joueur inscrit"

# --- FONCTION POUR CRÉER LE TABLEAU FF14 ---
def generer_tableau_ff14(tournoi):
    """Génère un tableau organisé par rôle pour FF14"""
    roles = {
        "DPS": {"emoji": "⚔️", "joueurs": []},
        "HEALER": {"emoji": "💉", "joueurs": []},
        "TANK": {"emoji": "🛡️", "joueurs": []},
        "Tout Role": {"emoji": "🎮", "joueurs": []},
        "BENCH": {"emoji": "🪑", "joueurs": []}
    }

    for entry in tournoi["inscrits"]:
        if "(" in entry and ")" in entry:
            mention = entry.split("(")[0].strip()
            role = entry.split("(")[1].split(")")[0].strip()
            if role in roles:
                roles[role]["joueurs"].append(mention)

    tableau = ""
    for role_code, info in roles.items():
        if info["joueurs"]:
            tableau += f"\n{info['emoji']} **{role_code}** ({len(info['joueurs'])} joueur{'s' if len(info['joueurs']) > 1 else ''})\n"
            tableau += "\n".join([f"• {joueur}" for joueur in info["joueurs"]])
            tableau += "\n"

    return tableau if tableau else "Aucun joueur inscrit"

# --- MENU DE SÉLECTION MULTIPLE WARHAMMER ---
class WarhammerSelect(Select):
    def __init__(self, message_id):
        options = [
            discord.SelectOption(label="Warhammer 40K", emoji="🚀", value="40K"),
            discord.SelectOption(label="Age of Sigmar", emoji="🛡️", value="AOS"),
            discord.SelectOption(label="Kill Team", emoji="🎯", value="KT"),
        ]
        super().__init__(
            placeholder="Choisissez vos formats (multi-choix)...", 
            options=options, 
            min_values=1, 
            max_values=3
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        tournoi = tournois.get(self.message_id)
        if not tournoi: 
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        
        # Vérifier si déjà inscrit
        if _user_already_registered(tournoi, user_id):
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
            return

        choices_str = ", ".join(self.values)
        user_entry = f"{interaction.user.mention} ({choices_str})"
        
        if tournoi["max_joueurs"] is None or len(tournoi["inscrits"]) < tournoi["max_joueurs"]:
            tournoi["inscrits"].append(user_entry)
            await interaction.response.send_message(f"✅ Inscrit en : **{choices_str}** !", ephemeral=True)
        else:
            tournoi["attente"].append(user_entry)
            await interaction.response.send_message(f"⏳ Tournoi complet, mis en attente ({choices_str})", ephemeral=True)

        sauvegarder_tournois()
        await update_message(interaction, self.message_id)

# --- MENU DE SÉLECTION FF14 ---
class FF14Select(Select):
    def __init__(self, message_id):
        options = [
            discord.SelectOption(label="DPS", emoji="⚔️", value="DPS"),
            discord.SelectOption(label="HEALER", emoji="💉", value="HEALER"),
            discord.SelectOption(label="TANK", emoji="🛡️", value="TANK"),
            discord.SelectOption(label="Tout Role", emoji="🎮", value="Tout Role"),
            discord.SelectOption(label="BENCH", emoji="🪑", value="BENCH"),
        ]
        super().__init__(
            placeholder="Choisissez votre rôle...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        tournoi = tournois.get(self.message_id)
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if _user_already_registered(tournoi, user_id):
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
            return

        role = self.values[0]
        user_entry = f"{interaction.user.mention} ({role})"

        if tournoi["max_joueurs"] is None or len(tournoi["inscrits"]) < tournoi["max_joueurs"]:
            tournoi["inscrits"].append(user_entry)
            await interaction.response.send_message(f"✅ Inscrit en : **{role}** !", ephemeral=True)
        else:
            tournoi["attente"].append(user_entry)
            await interaction.response.send_message(f"⏳ Tournoi complet, mis en attente ({role})", ephemeral=True)

        sauvegarder_tournois()
        await update_message(interaction, self.message_id)

# --- INTERFACE PRINCIPALE ---
class TournoiView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="✅ Rejoindre", style=discord.ButtonStyle.green, custom_id="join_btn")
    async def rejoindre(self, interaction: discord.Interaction, button: discord.ui.Button):
        tournoi = tournois.get(self.message_id)
        if not tournoi: 
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if _user_already_registered(tournoi, user_id):
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
            return
        
        if tournoi.get("type") == "ff14":
            view = View()
            view.add_item(FF14Select(self.message_id))
            await interaction.response.send_message("🎮 Sélectionnez votre rôle FF14 :", view=view, ephemeral=True)
        elif tournoi.get("type") == "warhammer":
            view = View()
            view.add_item(WarhammerSelect(self.message_id))
            await interaction.response.send_message("🎮 Sélectionnez vos formats Warhammer :", view=view, ephemeral=True)
        else:
            # Mode Tournoi Classique (Inscription directe)
            user_mention = interaction.user.mention
            if tournoi["max_joueurs"] is None or len(tournoi["inscrits"]) < tournoi["max_joueurs"]:
                tournoi["inscrits"].append(user_mention)
                await interaction.response.send_message("✅ Inscription réussie !", ephemeral=True)
            else:
                tournoi["attente"].append(user_mention)
                await interaction.response.send_message("⏳ En liste d'attente", ephemeral=True)
            
            sauvegarder_tournois()
            await update_message(interaction, self.message_id)

    @discord.ui.button(label="❌ Se désinscrire", style=discord.ButtonStyle.red, custom_id="leave_btn")
    async def desinscrire(self, interaction: discord.Interaction, button: discord.ui.Button):
        tournoi = tournois.get(self.message_id)
        if not tournoi: 
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return
            
        user_id = str(interaction.user.id)
        removed = False
        
        for lst in ["inscrits", "attente"]:
            for entry in tournoi[lst]:
                if _extract_user_id_from_entry(entry) == user_id:
                    tournoi[lst].remove(entry)
                    removed = True
                    break
            if removed: 
                break
                
        if removed:
            # Promouvoir quelqu'un de la liste d'attente
            if tournoi["attente"] and len(tournoi["inscrits"]) < (tournoi["max_joueurs"] or 9999):
                tournoi["inscrits"].append(tournoi["attente"].pop(0))
            
            await interaction.response.send_message("✅ Désinscrit avec succès.", ephemeral=True)
            sauvegarder_tournois()
            await update_message(interaction, self.message_id)
        else:
            await interaction.response.send_message("❌ Tu n'es pas inscrit.", ephemeral=True)

async def update_message(interaction, message_id):
    tournoi = tournois.get(message_id)
    if not tournoi: 
        return
    
    try:
        embed = discord.Embed(title=tournoi['titre'], color=tournoi.get('color', 0x3498db))
        embed.add_field(name="📍 Lieu", value=tournoi["lieu"], inline=True)
        embed.add_field(name="📅 Date", value=tournoi["date"], inline=True)
        if tournoi.get("heure"):
            embed.add_field(name="⏰ Heure", value=tournoi["heure"], inline=True)
        
        max_d = "∞" if tournoi['max_joueurs'] is None else str(tournoi['max_joueurs'])
        embed.add_field(name="👥 Inscrits", value=f"{len(tournoi['inscrits'])}/{max_d}", inline=False)
        
        # Affichage différent selon le type de tournoi
        if tournoi.get("type") == "warhammer":
            # Affichage en tableau par jeu
            tableau = generer_tableau_warhammer(tournoi)
            embed.add_field(name="⚔️ Répartition par jeu", value=tableau, inline=False)
        elif tournoi.get("type") == "ff14":
            tableau = generer_tableau_ff14(tournoi)
            embed.add_field(name="🎮 Répartition par rôle", value=tableau, inline=False)
        else:
            # Affichage classique
            embed.add_field(name="✅ Joueurs", value="\n".join(tournoi["inscrits"]) or "Aucun", inline=False)
        
        # Liste d'attente (commune aux deux types)
        if tournoi["attente"]:
            embed.add_field(name="⏳ Liste d'attente", value="\n".join(tournoi["attente"]), inline=False)
        
        msg = await interaction.channel.fetch_message(message_id)
        await msg.edit(embed=embed, view=TournoiView(message_id))
        
    except discord.NotFound:
        print(f"❌ Message {message_id} introuvable")
    except Exception as e:
        print(f"❌ Erreur update_message: {e}")

# --- COMMANDE /EVENT ---
@bot.tree.command(name="event", description="Créer un nouvel événement")
@app_commands.describe(
    template="Type d'événement", 
    titre="Nom de l'event", 
    lieu="Lieu", 
    date="Date", 
    max_joueurs="Places max (laisser vide = illimité)",
    heure="Heure (optionnel, ex: 19h ou 19h30)"
)
@app_commands.choices(template=[
    Choice(name="🏆 Tournoi (Standard / Jeu unique)", value="standard"),
    Choice(name="⚔️ Warhammer (Multiformat)", value="warhammer"),
    Choice(name="🎮 FF14 (Rôles)", value="ff14")
])
@app_commands.checks.has_permissions(administrator=True)
async def creer_tournoi(
    interaction: discord.Interaction,
    template: Choice[str],
    titre: str,
    lieu: str,
    date: str,
    max_joueurs: int = None,
    heure: str = None
):
    
    if template.value == "standard":
        full_title = f"🏆 {titre}"
        color = 0x3498db  # Bleu
    elif template.value == "warhammer":
        full_title = f"⚔️ [WARHAMMER] {titre}"
        color = 0x2c3e50  # Anthracite
    else:
        full_title = f"🎮 [FF14] {titre}"
        color = 0x6c5ce7  # Violet

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

    # ✅ PING @everyone avec allowed_mentions
    await interaction.response.send_message(
        content="@everyone", 
        embed=embed,
        allowed_mentions=discord.AllowedMentions(everyone=True)
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
        "color": color
    }
    
    await message.edit(view=TournoiView(message.id))
    sauvegarder_tournois()

@bot.event
async def on_ready():
    charger_tournois()
    # Réattacher les views aux messages existants
    for msg_id in tournois:
        bot.add_view(TournoiView(msg_id))

    if not verifier_rappels_evenements.is_running():
        verifier_rappels_evenements.start()
    
    await bot.tree.sync()
    print(f"🚀 Bot en ligne : {bot.user}")
    print(f"📊 {len(tournois)} tournois actifs")

# ✅ LANCEMENT DU BOT AVEC KEEP-ALIVE
keep_alive()
token = os.getenv("DISCORD_TOKEN") or os.getenv("TON_TOKEN_ICI")
if not token:
    raise RuntimeError("Token Discord introuvable. Définis DISCORD_TOKEN (ou TON_TOKEN_ICI).")

bot.run(token)