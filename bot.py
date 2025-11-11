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

# ========= CONFIG =========
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found! Set DISCORD_TOKEN in Render or create token.txt locally.")

PREFIX = "?"
EXPIRATION_YEARS = 4
LICENSE_CHANNEL_ID = 1436890841703645285  # logs channel

# ========= DISCORD SETUP =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

app = Flask(__name__)

# ---------- TEXT MEASUREMENT HELPER ----------
def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    """
    Returns (width, height) for text, compatible with Pillow ≥10 (no textsize).
    """
    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return (right - left, bottom - top)
    elif hasattr(draw, "textsize"):  # older Pillow fallback
        return draw.textsize(text, font=font)
    else:  # ultimate fallback
        try:
            left, top, right, bottom = font.getbbox(text)
            return (right - left, bottom - top)
        except Exception:
            return (len(text) * 10, 20)


# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height, issued, expires, lic_num):
    """Creates an official Lakeview City DMV Driver License"""
    W, H = 1000, 640
    img = Image.new("RGB", (W, H), (245, 247, 252))
    draw = ImageDraw.Draw(img)

    # Fonts
    try:
        font_header = ImageFont.truetype("arialbd.ttf", 44)
        font_bold = ImageFont.truetype("arialbd.ttf", 32)
        font_text = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except:
        font_header = font_bold = font_text = font_small = ImageFont.load_default()

    # Border
    draw.rounded_rectangle((8, 8, W - 8, H - 8), radius=25, outline=(170, 180, 200), width=4)

    # Blue header
    draw.rectangle((0, 0, W, 100), fill=(42, 86, 160))
    header_text = f"{username} | Driver's License"
    tw, th = measure_text(draw, header_text, font_header)
    draw.text(((W - tw) / 2, 30), header_text, fill="white", font=font_header)

    # Watermark
    watermark = "CITY OF LAKEVIEW • DMV • OFFICIAL USE ONLY  " * 3
    draw.text((30, 110), watermark[:95], fill=(90, 110, 150), font=font_small)

    # Avatar
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((240, 240))
            mask = Image.new("L", avatar.size, 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.rounded_rectangle((0, 0, 240, 240), radius=40, fill=255)
            avatar.putalpha(mask)
            img.paste(avatar, (60, 180), avatar)
            draw.rounded_rectangle((60, 180, 300, 420), radius=40, outline=(150, 160, 180), width=2)
        except Exception as e:
            print("[Avatar Error]", e)

    # Info Section
    base_x = 340
    y = 170
    spacing = 42
    color = (30, 30, 40)

    draw.text((base_x, y), roleplay_name or username, fill=color, font=font_bold)
    y += spacing + 10
    draw.text((base_x, y), f"Full Name: {roleplay_name or username}", fill=color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Age: {age or 'N/A'}", fill=color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Address: {address or 'N/A'}", fill=color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Eye Color: {eye_color or 'N/A'}", fill=color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Height: {height or 'N/A'}", fill=color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"License #: {lic_num}", fill=color, font=font_text)

    # DMV Seal
    cx, cy = 850, 500
    draw.ellipse((cx, cy, cx + 120, cy + 120), outline=(60, 90, 180), width=4)
    draw.text((cx + 38, cy + 45), "DMV", fill=(60, 90, 180), font=font_bold)

    # Notes Box
    draw.rounded_rectangle((40, 460, 960, 610), radius=20, outline=(150, 160, 180), width=2, fill=(240, 243, 250))
    draw.text((60, 470), "Notes", fill=(60, 90, 180), font=font_bold)
    draw.text((760, 470), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=color, font=font_text)
    draw.text((760, 510), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=color, font=font_text)
    draw.text((700, 580), "Lakeview City Roleplay", fill=(60, 90, 180), font=font_small)

    # Output
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out.read()



# ---------- FLASK WEBHOOK ----------
@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.get_json(force=True, silent=True) or {}
        print("[Webhook] Incoming data:", data)

        username = (data.get("roblox_username") or "").strip()
        display = (data.get("roblox_display") or "").strip()
        avatar_url = (data.get("roblox_avatar") or "").strip()
        product = data.get("product_name", "Driver License")
        discord_id = data.get("discord_id")

        # Roleplay data
        roleplay_name = (data.get("roleplay_name") or "").strip()
        age = (data.get("age") or "").strip()
        address = (data.get("address") or "").strip()
        eye_color = (data.get("eye_color") or "").strip()
        height = (data.get("height") or "").strip()

        if not username:
            return jsonify({"status": "error", "message": "Missing username"}), 400
        if not avatar_url or not avatar_url.startswith("http"):
            return jsonify({"status": "error", "message": f"Invalid avatar URL: {avatar_url}"}), 400

        # Download avatar
        avatar_bytes = None
        try:
            r = requests.get(avatar_url, timeout=10)
            if r.ok:
                avatar_bytes = r.content
        except Exception as e:
            print("[Avatar Download Error]", e)

        issued = datetime.utcnow()
        expires = issued + timedelta(days=365 * EXPIRATION_YEARS)
        lic_num = f"{username[:8].upper()}01-{expires.year}"

        img_data = create_license_image(
            username=username,
            avatar_bytes=avatar_bytes,
            roleplay_name=roleplay_name,
            age=age,
            address=address,
            eye_color=eye_color,
            height=height,
            issued=issued,
            expires=expires,
            lic_num=lic_num,
        )

        # Send DM if user ID provided
        if discord_id:
            async def send_dm():
                await bot.wait_until_ready()
                user = bot.get_user(int(discord_id))
                if user:
                    try:
                        await user.send(
                            f"📄 Here’s your official {product}!",
                            file=discord.File(io.BytesIO(img_data), filename=f"{roleplay_name or username}_license.png"),
                        )
                    except Exception as e:
                        print(f"[DM Error] {e}")

            bot.loop.create_task(send_dm())

        # Log to channel as backup
        channel = bot.get_channel(LICENSE_CHANNEL_ID)
        if channel:
            bot.loop.create_task(
                channel.send(
                    f"✅ License generated for **{roleplay_name or username}**",
                    file=discord.File(io.BytesIO(img_data), filename=f"{roleplay_name or username}_license.png"),
                )
            )

        return jsonify({"status": "ok", "message": "License created"}), 200

    except Exception as e:
        print(f"[Webhook Exception] {type(e).__name__}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------- BASIC COMMANDS ----------
@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 `{latency}ms`")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

# ---------- RUN ----------
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Starting Flask server for Render...")
    app.run(host="0.0.0.0", port=8080)
