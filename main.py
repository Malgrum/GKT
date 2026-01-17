import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
from discord.app_commands import Choice
import json
import os
from flask import Flask
from threading import Thread

# --- KEEP ALIVE (évite mise en veille Render) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot Discord en ligne !"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURATION ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

tournois = {}
TOURNOIS_FILE = "tournois.json"

# --- PERSISTANCE ---
def charger_tournois():
    global tournois
    if os.path.exists(TOURNOIS_FILE):
        try:
            with open(TOURNOIS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tournois = {int(k): v for k, v in data.items()}
                print(f"✅ {len(tournois)} tournois chargés.")
        except Exception as e:
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
        all_participants = tournoi["inscrits"] + tournoi["attente"]
        if any(user_id in p for p in all_participants):
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
        all_participants = tournoi["inscrits"] + tournoi["attente"]
        if any(user_id in p for p in all_participants):
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
            return

        if tournoi.get("type") == "warhammer":
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
                if user_id in entry:
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
        
        max_d = "∞" if tournoi['max_joueurs'] is None else str(tournoi['max_joueurs'])
        embed.add_field(name="👥 Inscrits", value=f"{len(tournoi['inscrits'])}/{max_d}", inline=False)
        
        # Affichage différent selon le type de tournoi
        if tournoi.get("type") == "warhammer":
            # Affichage en tableau par jeu
            tableau = generer_tableau_warhammer(tournoi)
            embed.add_field(name="⚔️ Répartition par jeu", value=tableau, inline=False)
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
    max_joueurs="Places max (laisser vide = illimité)"
)
@app_commands.choices(template=[
    Choice(name="🏆 Tournoi (Standard / Jeu unique)", value="standard"),
    Choice(name="⚔️ Warhammer (Multiformat)", value="warhammer")
])
@commands.has_permissions(administrator=True)
async def creer_tournoi(interaction: discord.Interaction, template: Choice[str], titre: str, lieu: str, date: str, max_joueurs: int = None):
    
    if template.value == "standard":
        full_title = f"🏆 {titre}"
        color = 0x3498db  # Bleu
    else:
        full_title = f"⚔️ [WARHAMMER] {titre}"
        color = 0x2c3e50  # Anthracite

    embed = discord.Embed(title=full_title, color=color)
    embed.add_field(name="📍 Lieu", value=lieu, inline=True)
    embed.add_field(name="📅 Date", value=date, inline=True)
    embed.add_field(name="👥 Inscrits", value=f"0/{(max_joueurs or '∞')}", inline=False)
    
    if template.value == "warhammer":
        embed.add_field(name="⚔️ Répartition par jeu", value="Aucun joueur inscrit", inline=False)
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
    
    await bot.tree.sync()
    print(f"🚀 Bot en ligne : {bot.user}")
    print(f"📊 {len(tournois)} tournois actifs")

# ✅ LANCEMENT DU BOT AVEC KEEP-ALIVE
keep_alive()
bot.run(os.getenv('TON_TOKEN_ICI'))