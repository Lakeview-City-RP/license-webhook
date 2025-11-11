from __future__ import annotations

# --- stdlib
import os, io, json, asyncio
from datetime import datetime
from threading import Thread
from typing import Optional

# --- third-party
import aiohttp, requests
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, jsonify

# --- discord.py
import discord
from discord.ext import commands

# ========= TOKEN & CONFIG =========
TOKEN = os.getenv("DISCORD_TOKEN")

# ✅ Optional local fallback for testing
if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found! Set DISCORD_TOKEN in Render or create token.txt locally.")

GUILD_ID = int(os.getenv("GUILD_ID", "0"))
PREFIX = "?"
LICENSES_DIR = "licenses"
JSON_FILE = "licenses.json"
EXPIRATION_YEARS = 4
UNLIMITED_CREATORS = {934850555728252978, 1303898031032373309}
BLOXLINK_DEBUG = False

# ========= DISCORD SETUP =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

os.makedirs(LICENSES_DIR, exist_ok=True)
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

# ---------- JSON HELPERS ----------
def load_licenses():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_licenses(data):
    tmp = JSON_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, JSON_FILE)

# ---------- BLOXLINK ----------
async def fetch_bloxlink(discord_id: int, guild_id: Optional[int] = None):
    guild_id = guild_id or GUILD_ID
    url = f"https://api.blox.link/v4/public/guilds/{guild_id}/discord-to-roblox/{discord_id}"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    rid = j.get("robloxID")
                    username = j.get("resolved", {}).get("roblox", {}).get("username")
                    return rid, username, "bloxlink"
                return None, None, "not_verified"
    except Exception as e:
        print(f"[Bloxlink Error] {e}")
        return None, None, "error"

# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, fields, issued, expires, lic_num, description=""):
    W, H = 1000, 620
    img = Image.new("RGBA", (W, H), (30, 31, 34, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 44)
        font_label = ImageFont.truetype("arial.ttf", 22)
        font_value = ImageFont.truetype("arialbd.ttf", 26)
    except:
        font_title = font_label = font_value = ImageFont.load_default()

    draw.rectangle((0, 0, W, 120), fill=(52, 56, 66))
    tw, _ = draw.textsize(username, font=font_title)
    draw.text(((W - tw) / 2, 35), f"{username} • City License", fill="white", font=font_title)

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG")
    out.seek(0)
    return out.read()

# ---------- LICENSE COMMAND ----------
@bot.command()
async def license(ctx):
    await ctx.send("✅ License system is ready.")
    try:
        await ctx.message.delete()
    except:
        pass

# ---------- FLASK APP ----------
app = Flask(__name__)

# ✅ Test route (to confirm Flask works)
@app.route("/")
def index():
    return "✅ Flask is working!"

# ✅ Main webhook for BotGhost → Python
@app.route("/license", methods=["POST"])
def license_endpoint():
    data = request.json
    username = data.get("username")
    avatar_url = data.get("avatar")
    product = data.get("product_name", "VIP License")

    if not all([username, avatar_url]):
        return jsonify({"status": "error", "message": "Missing data"}), 400

    try:
        avatar_bytes = requests.get(avatar_url).content
        img_data = create_license_image(username, avatar_bytes, {}, datetime.utcnow(), datetime.utcnow(), "AUTO")

        # Send image to your Discord channel
        channel = bot.get_channel(1436890841703645285)  # Replace with your channel ID
        if channel:
            bot.loop.create_task(channel.send(file=discord.File(io.BytesIO(img_data), filename="license.png")))

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- BOT COMMAND ----------
@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 `{latency}ms`")

# ---------- BOT STARTUP ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

# ---------- RUN DISCORD BOT + FLASK ----------
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🚀 Starting Flask server for Render...")
    app.run(host="0.0.0.0", port=8080)
