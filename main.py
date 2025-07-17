import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

tournoi = {
    "lieu": None,
    "date": None,
    "max_joueurs": 0,
    "inscrits": [],
    "attente": [],
    "message_id": None
}

class TournoiView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Rejoindre", style=discord.ButtonStyle.green)
    async def rejoindre(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.name

        if user in tournoi["inscrits"]:
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
        elif user in tournoi["attente"]:
            await interaction.response.send_message("Tu es déjà en liste d'attente.", ephemeral=True)
        elif len(tournoi["inscrits"]) < tournoi["max_joueurs"]:
            tournoi["inscrits"].append(user)
            await interaction.response.send_message("Tu es inscrit au tournoi !", ephemeral=True)
        else:
            tournoi["attente"].append(user)
            await interaction.response.send_message("Tournoi complet, tu es en liste d’attente ⏳", ephemeral=True)

        await update_message(interaction)

    @discord.ui.button(label="❌ Se désinscrire", style=discord.ButtonStyle.red)
    async def desinscrire(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.name

        if user in tournoi["inscrits"]:
            tournoi["inscrits"].remove(user)

            # Ajouter le 1er de la liste d'attente s'il existe
            if tournoi["attente"]:
                prochain = tournoi["attente"].pop(0)
                tournoi["inscrits"].append(prochain)
        elif user in tournoi["attente"]:
            tournoi["attente"].remove(user)
        else:
            await interaction.response.send_message("Tu n’es pas inscrit.", ephemeral=True)
            return

        await interaction.response.send_message("Tu as été désinscrit.", ephemeral=True)
        await update_message(interaction)

async def update_message(interaction):
    embed = discord.Embed(title="🏆 Tournoi", color=discord.Color.blue())
    embed.add_field(name="📍 Lieu", value=tournoi["lieu"], inline=True)
    embed.add_field(name="📅 Date", value=tournoi["date"], inline=True)
    embed.add_field(name="👥 Inscrits", value=f"{len(tournoi['inscrits'])}/{tournoi['max_joueurs']}", inline=False)
    embed.add_field(name="✅ Joueurs", value="\n".join(tournoi["inscrits"]) or "Aucun", inline=False)
    embed.add_field(name="⏳ Attente", value="\n".join(tournoi["attente"]) or "Aucune", inline=False)

    channel = interaction.channel
    if tournoi["message_id"]:
        try:
            msg = await channel.fetch_message(tournoi["message_id"])
            await msg.edit(embed=embed, view=TournoiView())
        except discord.Forbidden:
            print("❌ Bot manque de permissions pour modifier le message")
        except discord.NotFound:
            print("❌ Message original introuvable")
        except Exception as e:
            print(f"❌ Erreur: {e}")

@bot.command(name="event")
@commands.has_permissions(administrator=True)
async def creer_tournoi(ctx, titre: str, lieu: str, date: str, max_joueurs: int):
    tournoi["titre"] = titre
    tournoi["lieu"] = lieu
    tournoi["date"] = date
    tournoi["max_joueurs"] = max_joueurs
    tournoi["inscrits"] = []
    tournoi["attente"] = []

    embed = discord.Embed(title=f"🏆 {titre}", color=discord.Color.blue())
    embed.add_field(name="📍 Lieu", value=lieu, inline=True)
    embed.add_field(name="📅 Date", value=date, inline=True)
    embed.add_field(name="👥 Inscrits", value=f"0/{max_joueurs}", inline=False)
    embed.add_field(name="✅ Joueurs", value="Aucun", inline=False)
    embed.add_field(name="⏳ Attente", value="Aucune", inline=False)

    try:
        message = await ctx.send(embed=embed, view=TournoiView())
        tournoi["message_id"] = message.id
        print("✅ Tournoi créé avec succès!")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour envoyer des messages avec embed.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la création: {e}")

bot.run("MTM5NTM1Mjk0MTg3OTIzNDY2MA.GyVJBj.IyqeHOmKhTdvo_JGfYgO2ptYR5z2oQ9qVoqoro")