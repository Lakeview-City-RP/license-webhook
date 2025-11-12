from __future__ import annotations

# --- stdlib
import os, io, json, asyncio
from datetime import datetime
from threading import Thread
from typing import Optional

# --- third-party
import aiohttp, requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

# ========= DISCORD SETUP =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

os.makedirs(LICENSES_DIR, exist_ok=True)
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height, issued, expires, lic_num):
    """Creates a modern Lakeview City DMV Driver License"""
    W, H = 800, 500
    img = Image.new("RGB", (W, H), (240, 245, 255))
    draw = ImageDraw.Draw(img)

    # Colors
    header_color = (35, 70, 140)
    text_color = (25, 25, 35)
    accent = (60, 110, 200)

    # Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 48)
        font_bold = ImageFont.truetype("arialbd.ttf", 26)
        font_text = ImageFont.truetype("arial.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_title = font_bold = font_text = font_small = ImageFont.load_default()

    # Rounded background
    base = Image.new("RGB", (W, H), (255, 255, 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=40, fill=255)
    img.paste(base, (0, 0), mask)

    # Header
    draw.rounded_rectangle((0, 0, W, 90), radius=40, fill=header_color)
    title = "LAKEVIEW CITY DRIVER’S LICENSE"
    try:
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(title, font=font_title)
    draw.text(((W - tw) / 2, 20), title, fill="white", font=font_title)

    # Banner line
    banner_text = "CITY OF LAKEVIEW • OFFICIAL USE ONLY"
    try:
        bbox = draw.textbbox((0, 0), banner_text, font=font_small)
        bw = bbox[2] - bbox[0]
    except AttributeError:
        bw, _ = draw.textsize(banner_text, font=font_small)
    draw.rectangle((0, 90, W, 115), fill=(220, 225, 245))
    draw.text(((W - bw) / 2, 93), banner_text, fill=(70, 90, 140), font=font_small)

    # Avatar
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((180, 180))
            amask = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(amask).rounded_rectangle((0, 0, 180, 180), radius=40, fill=255)
            avatar.putalpha(amask)
            img.paste(avatar, (50, 160), avatar)
            draw.rounded_rectangle((50, 160, 230, 340), radius=40, outline=(140, 150, 170), width=3)
        except Exception as e:
            print("[Avatar Error]", e)

    # Info layout
    x = 260
    y = 150
    spacing = 38

    draw.text((x, y), "IDENTITY", fill=accent, font=font_bold)
    y += spacing
    draw.text((x, y), f"Name: {roleplay_name or username}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((x, y), f"Age: {age or 'N/A'}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((x, y), f"Address: {address or 'N/A'}", fill=text_color, font=font_bold)

    y += spacing + 10
    draw.text((x, y), "PHYSICAL INFO", fill=accent, font=font_bold)
    y += spacing
    draw.text((x, y), f"Eye Color: {eye_color or 'N/A'}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((x, y), f"Height: {height or 'N/A'}", fill=text_color, font=font_bold)

    y += spacing + 10
    draw.text((x, y), "DMV INFO", fill=accent, font=font_bold)
    y += spacing
    draw.text((x, y), f"License #: {lic_num}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((x, y), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((x, y), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=text_color, font=font_bold)

    # Notes
    draw.rounded_rectangle((30, 370, W - 30, H - 20), radius=25, outline=(160, 170, 190), width=2, fill=(235, 238, 250))
    draw.text((50, 380), "DMV NOTES", fill=accent, font=font_bold)
    draw.text(
        (50, 415),
        "This license is property of the Lakeview City DMV.\n"
        "Tampering or duplication is punishable by law.\n"
        "Verify authenticity at https://lakeviewdmv.gov",
        fill=(60, 60, 70),
        font=font_small,
    )

    # Holographic overlay (gradient shimmer)
    holo = Image.new("RGBA", img.size)
    hdraw = ImageDraw.Draw(holo)
    for i in range(H):
        color = (
            int(180 + 50 * (i / H)),
            int(200 + 30 * (1 - i / H)),
            255,
            int(40 + 30 * (i / H)),
        )
        hdraw.line((0, i, W, i), fill=color)
    holo = holo.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img.convert("RGBA"), holo)

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out.read()

# ---------- FLASK APP ----------
app = Flask(__name__)

@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json
        username = data.get("roblox_username")
        display = data.get("roblox_display")
        avatar_url = data.get("roblox_avatar")
        roleplay_name = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye_color = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")
        product = data.get("product_name", "Driver License")

        if not username or not avatar_url or not avatar_url.startswith("http"):
            return jsonify({"status": "error", "message": "Invalid avatar URL or username"}), 400

        avatar_bytes = requests.get(avatar_url).content
        img_data = create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height, datetime.utcnow(), datetime.utcnow(), "AUTO")

        async def send_license():
            await bot.wait_until_ready()
            channel = bot.get_channel(1436890841703645285)
            if not channel:
                print("[Webhook Error] License channel not found")
                return

            file = discord.File(io.BytesIO(img_data), filename=f"{username}_license.png")

            await channel.send(file=file)
            try:
                if discord_id:
                    user = bot.get_user(int(discord_id))
                    if user:
                        await user.send(file=file)
            except Exception as e:
                print(f"[DM Error] {e}")

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok", "message": "License created"}), 200

    except Exception as e:
        print(f"[Webhook Exception] {type(e).__name__}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- BASIC COMMAND ----------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! 🏓 `{round(bot.latency * 1000)}ms`")

@bot.command()
async def license(ctx):
    await ctx.send("✅ License system online and ready.")
    try:
        await ctx.message.delete()
    except:
        pass

# ---------- BOT READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

# ---------- RUN ----------
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🚀 Starting Flask server for Render...")
    app.run(host="0.0.0.0", port=8080)
