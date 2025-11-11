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
    W, H = 1000, 640
    img = Image.new("RGB", (W, H), (236, 240, 250))
    draw = ImageDraw.Draw(img)

    # Colors
    header_color = (35, 70, 140)
    text_color = (25, 25, 35)
    accent = (80, 120, 190)

    # Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 54)
        font_bold = ImageFont.truetype("arialbd.ttf", 30)
        font_text = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = font_bold = font_text = font_small = ImageFont.load_default()

    # Rounded outer card
    draw.rounded_rectangle((8, 8, W - 8, H - 8), radius=40, fill=(250, 251, 255), outline=(180, 190, 210), width=4)

    # Header bar
    draw.rounded_rectangle((0, 0, W, 100), radius=20, fill=header_color)
    title = f"{username} | Driver's License"
    try:
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(title, font=font_title)
    draw.text(((W - tw) / 2, 25), title, fill="white", font=font_title)

    # Watermark / pattern
    wm_text = "CITY OF LAKEVIEW DMV • OFFICIAL USE ONLY  " * 3
    draw.text((30, 110), wm_text[:95], fill=(100, 120, 160), font=font_small)

    # Avatar
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((240, 240))
            mask = Image.new("L", avatar.size, 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.rounded_rectangle((0, 0, 240, 240), radius=45, fill=255)
            avatar.putalpha(mask)
            img.paste(avatar, (70, 180), avatar)
            draw.rounded_rectangle((70, 180, 310, 420), radius=45, outline=(150, 160, 180), width=3)
        except Exception as e:
            print("[Avatar Error]", e)

    # Info block
    base_x = 360
    y = 170
    spacing = 45

    draw.text((base_x, y), roleplay_name or username, fill=text_color, font=font_bold)
    y += spacing + 10
    draw.text((base_x, y), f"Full Name: {roleplay_name or username}", fill=text_color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Age: {age or 'N/A'}", fill=text_color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Address: {address or 'N/A'}", fill=text_color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Eye Color: {eye_color or 'N/A'}", fill=text_color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"Height: {height or 'N/A'}", fill=text_color, font=font_text)
    y += spacing
    draw.text((base_x, y), f"License #: {lic_num}", fill=text_color, font=font_text)

    # Notes / footer
    draw.rounded_rectangle((40, 460, 960, 610), radius=25, outline=(150, 160, 180), width=2, fill=(240, 243, 250))
    draw.text((60, 470), "Notes", fill=accent, font=font_bold)
    draw.text((760, 470), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=text_color, font=font_text)
    draw.text((760, 510), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=text_color, font=font_text)
    draw.text((700, 580), "Lakeview City Roleplay", fill=accent, font=font_small)

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

            embed = discord.Embed(
                title="📇 Driver License Issued",
                description=f"**{roleplay_name or username}** has been issued a new **Driver’s License**!",
                color=0x4A90E2
            )
            embed.add_field(name="Name", value=roleplay_name or username, inline=True)
            embed.add_field(name="Age", value=age or "N/A", inline=True)
            embed.add_field(name="Eye Color", value=eye_color or "N/A", inline=True)
            embed.add_field(name="Address", value=address or "N/A", inline=False)
            embed.set_footer(text=f"Issued {datetime.utcnow().strftime('%Y-%m-%d')}")
            embed.set_thumbnail(url=avatar_url)

            user_mention = f"<@{discord_id}>" if discord_id else username
            file = discord.File(io.BytesIO(img_data), filename=f"{username}_license.png")

            # Send to channel
            await channel.send(content=f"{user_mention}, your license has been issued ✅", embed=embed, file=file)

            # Try DM
            try:
                user = bot.get_user(int(discord_id))
                if user:
                    dm_embed = discord.Embed(
                        title="🏙️ Lakeview City DMV",
                        description=f"Here is your official **Driver’s License**, {roleplay_name or username}!",
                        color=0x4A90E2
                    )
                    dm_embed.set_thumbnail(url=avatar_url)
                    dm_embed.set_footer(text="Lakeview City Roleplay | DMV Records")
                    await user.send(embed=dm_embed, file=file)
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
