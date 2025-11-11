from __future__ import annotations

# --- stdlib
import os, io, json, asyncio
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

# --- third-party
import aiohttp, requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
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
    """Draws a clean, centered license layout"""
    W, H = 1000, 600
    bg_color = (240, 243, 249)
    border_color = (180, 188, 200)
    accent = (53, 97, 180)

    img = Image.new("RGBA", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Rounded border
    radius = 25
    border = Image.new("RGBA", (W, H))
    b_draw = ImageDraw.Draw(border)
    b_draw.rounded_rectangle((0, 0, W-1, H-1), radius, outline=border_color, width=4)
    img.alpha_composite(border)

    # Load fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 40)
        font_label = ImageFont.truetype("arial.ttf", 24)
        font_value = ImageFont.truetype("arialbd.ttf", 28)
    except:
        font_title = font_label = font_value = ImageFont.load_default()

    # Avatar circle (if provided)
    if avatar_bytes:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((200, 200))
        mask = Image.new("L", (200, 200), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 200, 200), fill=255)
        avatar = ImageOps.fit(avatar, (200, 200))
        avatar.putalpha(mask)
        img.paste(avatar, (60, 170), avatar)

    # Header
    draw.text((300, 40), f"{username} • City License", fill=accent, font=font_title)

    # License details
    draw.text((300, 180), f"License #: {lic_num}", fill="black", font=font_value)
    draw.text((300, 230), f"Product: {description or 'Driver License'}", fill="black", font=font_value)

    draw.text((300, 310), f"Issued: {issued.strftime('%Y-%m-%d')}", fill="black", font=font_label)
    draw.text((300, 350), f"Expires: {expires.strftime('%Y-%m-%d')}", fill="black", font=font_label)

    draw.text((300, 420), f"Authorized by: Lakeview City DMV", fill=accent, font=font_label)

    # DMV circle bottom-right
    draw.ellipse((830, 430, 950, 550), outline=accent, width=5)
    draw.text((860, 470), "DMV", fill=accent, font=font_value)

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

def _looks_like_template(v: str) -> bool:
    return isinstance(v, str) and "{{" in v and "}}" in v

@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.get_json(force=True, silent=True) or {}
        print("[Webhook] Incoming data:", data)

        username   = (data.get("roblox_username") or "").strip()
        display    = (data.get("roblox_display")  or "").strip()
        avatar_url = (data.get("roblox_avatar")   or "").strip()
        roblox_id  = data.get("roblox_id")
        product    = data.get("product_name", "Driver License")

        if _looks_like_template(username):
            username = display or username

        # Fetch avatar if missing or template-style
        if (not avatar_url or _looks_like_template(avatar_url)) and roblox_id:
            try:
                r = requests.get(
                    "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                    params={"userIds": roblox_id, "size": "420x420", "format": "Png", "isCircular": "false"},
                    timeout=8,
                )
                if r.ok:
                    j = r.json()
                    if j.get("data"):
                        avatar_url = j["data"][0].get("imageUrl") or avatar_url
            except Exception as e:
                print("[Avatar Fetch Error]", e)

        if not username:
            return jsonify({"status": "error", "message": "Missing username"}), 400
        if not avatar_url or not avatar_url.startswith("http"):
            return jsonify({"status": "error", "message": f"Invalid avatar URL: {avatar_url}"}), 400

        # Download avatar
        avatar_bytes = None
        try:
            avatar_bytes = requests.get(avatar_url, timeout=10).content
        except Exception as e:
            print("[Avatar Download Error]", e)

        issued = datetime.utcnow()
        expires = issued + timedelta(days=365 * EXPIRATION_YEARS)
        lic_num = f"{username[:4].upper()}-{issued.year}"

        img_data = create_license_image(username, avatar_bytes, {}, issued, expires, lic_num, product)

        # Send to Discord
        channel = bot.get_channel(1436890841703645285)
        if channel:
            bot.loop.create_task(
                channel.send(file=discord.File(io.BytesIO(img_data), filename=f"{username}_license.png"))
            )

        return jsonify({"status": "ok", "message": "License created"}), 200

    except Exception as e:
        print(f"[Webhook Exception] {type(e).__name__}: {e}")
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
