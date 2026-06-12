from __future__ import annotations

import discord
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

tournois: dict[int, dict] = {}
TOURNOIS_FILE = "tournois.json"
