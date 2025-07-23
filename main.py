import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View


intents = discord.Intents.all()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionnaire pour stocker plusieurs tournois (clé = message_id)
tournois = {}

authorized_accounts = []

class TournoiView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="✅ Rejoindre", style=discord.ButtonStyle.green)
    async def rejoindre(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.name
        tournoi = tournois.get(self.message_id)
        
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        if user in tournoi["inscrits"]:
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
        elif user in tournoi["attente"]:
            await interaction.response.send_message("Tu es déjà en liste d'attente.", ephemeral=True)
        elif tournoi["max_joueurs"] is None or len(tournoi["inscrits"]) < tournoi["max_joueurs"]:
            tournoi["inscrits"].append(user)
            await interaction.response.send_message("Tu es inscrit au tournoi !", ephemeral=True)
        else:
            tournoi["attente"].append(user)
            await interaction.response.send_message("Tournoi complet, tu es en liste d'attente ⏳", ephemeral=True)

        await update_message(interaction, self.message_id)

    @discord.ui.button(label="❌ Se désinscrire", style=discord.ButtonStyle.red)
    async def desinscrire(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.name
        tournoi = tournois.get(self.message_id)
        
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        if user in tournoi["inscrits"]:
            tournoi["inscrits"].remove(user)

            # Ajouter le 1er de la liste d'attente s'il existe
            if tournoi["attente"]:
                prochain = tournoi["attente"].pop(0)
                tournoi["inscrits"].append(prochain)
        elif user in tournoi["attente"]:
            tournoi["attente"].remove(user)
        else:
            await interaction.response.send_message("Tu n'es pas inscrit.", ephemeral=True)
            return

        await interaction.response.send_message("Tu as été désinscrit.", ephemeral=True)
        await update_message(interaction, self.message_id)

async def update_message(interaction, message_id):
    tournoi = tournois.get(message_id)
    if not tournoi:
        return
        
    embed = discord.Embed(title=f"🏆 {tournoi['titre']}", color=discord.Color.blue())
    embed.add_field(name="📍 Lieu", value=tournoi["lieu"], inline=True)
    embed.add_field(name="📅 Date", value=tournoi["date"], inline=True)
    max_display = "∞" if tournoi['max_joueurs'] is None else str(tournoi['max_joueurs'])
    embed.add_field(name="👥 Inscrits", value=f"{len(tournoi['inscrits'])}/{max_display}", inline=False)
    embed.add_field(name="✅ Joueurs", value="\n".join(tournoi["inscrits"]) or "Aucun", inline=False)
    embed.add_field(name="⏳ Attente", value="\n".join(tournoi["attente"]) or "Aucune", inline=False)

    channel = interaction.channel
    try:
        msg = await channel.fetch_message(message_id)
        await msg.edit(embed=embed, view=TournoiView(message_id))
    except discord.Forbidden:
        print("❌ Bot manque de permissions pour modifier le message")
    except discord.NotFound:
        print("❌ Message original introuvable")
    except Exception as e:
        print(f"❌ Erreur: {e}")

@bot.tree.command(name="event", description="Crée un tournoi")
@commands.has_permissions(administrator=True)
@app_commands.describe(titre="Titre du tournoi", lieu="Lieu du tournoi", date="Date du tournoi (format libre)", max_joueurs="Nombre maximum de joueurs (optionnel, infini si vide)")
async def creer_tournoi(interaction: discord.Interaction, titre: str, lieu: str, date: str, max_joueurs: int = None):
    max_display = "∞" if max_joueurs is None else str(max_joueurs)
    embed = discord.Embed(title=f"🏆 {titre}", color=discord.Color.blue())
    embed.add_field(name="📍 Lieu", value=lieu, inline=True)
    embed.add_field(name="📅 Date", value=date, inline=True)
    embed.add_field(name="👥 Inscrits", value=f"0/{max_display}", inline=False)
    embed.add_field(name="✅ Joueurs", value="Aucun", inline=False)
    embed.add_field(name="⏳ Attente", value="Aucune", inline=False)

    try:
        # Créer une vue temporaire pour envoyer le message
        temp_view = TournoiView(None)
        await interaction.response.send_message(content="@everyone", embed=embed, view=temp_view)
        message = await interaction.original_response()
        
        # Créer les données du tournoi avec l'ID du message
        tournois[message.id] = {
            "titre": titre,
            "lieu": lieu,
            "date": date,
            "max_joueurs": max_joueurs,
            "inscrits": [],
            "attente": []
        }
        
        # Mettre à jour avec la bonne vue qui a le message_id
        await message.edit(embed=embed, view=TournoiView(message.id))
        print(f"✅ Tournoi '{titre}' créé avec succès!")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Je n'ai pas les permissions pour envoyer des messages avec embed.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de la création: {e}")

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commande(s) sync")
    except Exception as e:
        print(e)

bot.run("MTM5NTM1Mjk0MTg3OTIzNDY2MA.GyVJBj.IyqeHOmKhTdvo_JGfYgO2ptYR5z2oQ9qVoqoro")
