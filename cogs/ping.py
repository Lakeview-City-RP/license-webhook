import discord
from discord.ext import commands

bot = commands.Bot(command_prefix='?', intents=discord.Intents.all())

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)  # Convert to ms
    await ctx.send(f"Pong! 🏓 `{latency}ms`")

bot.run("YOUR_BOT_TOKEN"