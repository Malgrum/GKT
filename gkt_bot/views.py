from __future__ import annotations

import discord
from discord.ui import Select, View

from .formatting import extract_user_id_from_entry, user_already_registered
from .state import tournois
from .storage import sauvegarder_tournois


class WarhammerSelect(Select):
    def __init__(self, message_id: int):
        options = [
            discord.SelectOption(label="Warhammer 40K", emoji="🚀", value="40K"),
            discord.SelectOption(label="Age of Sigmar", emoji="🛡️", value="AOS"),
            discord.SelectOption(label="Kill Team", emoji="🎯", value="KT"),
        ]
        super().__init__(
            placeholder="Choisissez vos formats (multi-choix)...",
            options=options,
            min_values=1,
            max_values=3,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        tournoi = tournois.get(self.message_id)
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if user_already_registered(tournoi, user_id):
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

        from .messages import update_message

        await update_message(interaction, self.message_id)


class FF14Select(Select):
    def __init__(self, message_id: int):
        options = [
            discord.SelectOption(label="DPS", emoji="⚔️", value="DPS"),
            discord.SelectOption(label="HEALER", emoji="💉", value="HEALER"),
            discord.SelectOption(label="TANK", emoji="🛡️", value="TANK"),
            discord.SelectOption(label="Tout Role", emoji="🎮", value="Tout Role"),
            discord.SelectOption(label="BENCH", emoji="🪑", value="BENCH"),
            discord.SelectOption(label="Pas Dispo", emoji="❌", value="Pas Dispo"),
        ]
        super().__init__(
            placeholder="Choisissez votre rôle...",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        tournoi = tournois.get(self.message_id)
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if user_already_registered(tournoi, user_id):
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

        from .messages import update_message

        await update_message(interaction, self.message_id)


class TournoiView(View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="✅ Rejoindre", style=discord.ButtonStyle.green, custom_id="join_btn")
    async def rejoindre(self, interaction: discord.Interaction, button: discord.ui.Button):
        tournoi = tournois.get(self.message_id)
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if user_already_registered(tournoi, user_id):
            await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)
            return

        if tournoi.get("type") == "ff14":
            view = View()
            view.add_item(FF14Select(self.message_id))
            await interaction.response.send_message("🎮 Sélectionnez votre rôle FF14 :", view=view, ephemeral=True)
            return

        if tournoi.get("type") == "warhammer":
            view = View()
            view.add_item(WarhammerSelect(self.message_id))
            await interaction.response.send_message("🎮 Sélectionnez vos formats Warhammer :", view=view, ephemeral=True)
            return

        user_mention = interaction.user.mention
        if tournoi["max_joueurs"] is None or len(tournoi["inscrits"]) < tournoi["max_joueurs"]:
            tournoi["inscrits"].append(user_mention)
            await interaction.response.send_message("✅ Inscription réussie !", ephemeral=True)
        else:
            tournoi["attente"].append(user_mention)
            await interaction.response.send_message("⏳ En liste d'attente", ephemeral=True)

        sauvegarder_tournois()

        from .messages import update_message

        await update_message(interaction, self.message_id)

    @discord.ui.button(label="❌ Se désinscrire", style=discord.ButtonStyle.red, custom_id="leave_btn")
    async def desinscrire(self, interaction: discord.Interaction, button: discord.ui.Button):
        tournoi = tournois.get(self.message_id)
        if not tournoi:
            await interaction.response.send_message("Tournoi introuvable.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        removed = False

        for bucket_name in ["inscrits", "attente"]:
            for entry in list(tournoi[bucket_name]):
                if extract_user_id_from_entry(entry) == user_id:
                    tournoi[bucket_name].remove(entry)
                    removed = True
                    break
            if removed:
                break

        if not removed:
            await interaction.response.send_message("❌ Tu n'es pas inscrit.", ephemeral=True)
            return

        if tournoi["attente"] and len(tournoi["inscrits"]) < (tournoi["max_joueurs"] or 9999):
            tournoi["inscrits"].append(tournoi["attente"].pop(0))

        await interaction.response.send_message("✅ Désinscrit avec succès.", ephemeral=True)
        sauvegarder_tournois()

        from .messages import update_message

        await update_message(interaction, self.message_id)
