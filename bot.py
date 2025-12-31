import os
import discord
from discord.ext import commands

def load_token() -> str:
    token = os.getenv("DISCORD_TOKEN")
    if not token and os.path.exists("token.txt"):
        with open("token.txt", "r", encoding="utf-8") as f:
            token = f.read().strip()
    if not token:
        raise RuntimeError("❌ Discord token not found (DISCORD_TOKEN or token.txt).")
    return token

TOKEN = load_token()

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="?", intents=intents)

@bot.event
async def setup_hook():
    await bot.load_extension("cogs.license_webhook")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.erlc_application")
    await bot.load_extension("cogs.dept_roster")
    print("✅ Loaded: cogs.license_webhook")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

bot.run(TOKEN)
