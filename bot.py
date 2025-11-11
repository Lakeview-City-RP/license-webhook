from __future__ import annotations

# --- stdlib
import os, io, json, asyncio
from datetime import datetime, timedelta
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
    """Draws a clean, centered DMV-style license card with proper text spacing."""
    W, H = 1000, 600
    bg_color = (245, 247, 252)
    accent = (60, 90, 180)
    border = (180, 190, 210)
    text_col = (25, 25, 30)

    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Border
    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=25, outline=border, width=4)

    # Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 38)
        font_label = ImageFont.truetype("arial.ttf", 26)
        font_value = ImageFont.truetype("arialbd.ttf", 28)
    except:
        font_title = font_label = font_value = ImageFont.load_default()

    # Header — clean centered username
    header_text = f"{username} | City License"
    text_w, _ = draw.textsize(header_text, font=font_title)
    draw.text(((W - text_w) / 2, 35), header_text, fill=accent, font=font_title)

    # Avatar placement (left)
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((220, 220))
            mask = Image.new("L", avatar.size, 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.ellipse((0, 0, 220, 220), fill=255)
            avatar.putalpha(mask)
            img.paste(avatar, (80, 180), avatar)
        except Exception as e:
            print(f"[Avatar Drawing Error] {e}")

    # Info area
    start_x = 360
    y = 180
    spacing = 45

    draw.text((start_x, y), f"License #: {lic_num}", fill=text_col, font=font_value)
    y += spacing
    draw.text((start_x, y), f"Product: {description or 'Driver License'}", fill=text_col, font=font_value)
    y += spacing
    draw.text((start_x, y), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=text_col, font=font_label)
    y += spacing
    draw.text((start_x, y), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=text_col, font=font_label)

    # Footer text
    footer_text = "Authorized by Lakeview City DMV"
    ft_w, _ = draw.textsize(footer_text, font=font_label)
    draw.text(((W - ft_w) / 2, H - 80), footer_text, fill=accent, font=font_label)

    # DMV Seal
    seal_x, seal_y = 820, 420
    draw.ellipse((seal_x, seal_y, seal_x + 120, seal_y + 120), outline=accent, width=4)
    draw.text((seal_x + 42, seal_y + 48), "DMV", fill=accent, font=font_value)

    # Save
    out = io.BytesIO()
    img.save(out, "PNG")
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

        # Fetch avatar if missing
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

        # ✅ Validate and download avatar
        avatar_bytes = None
        try:
            r = requests.get(avatar_url, timeout=10)
            if r.ok:
                avatar_bytes = r.content
            else:
                print("[Avatar Fetch] Failed with status:", r.status_code)
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
