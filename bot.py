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
def create_license_image(username, avatar_bytes, fields, issued, expires, lic_num, description="Driver's License"):
    """Creates an official-style Lakeview DMV license card."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

    # Rounded border
    draw.rounded_rectangle((8, 8, W - 8, H - 8), radius=25, outline=(170, 180, 200), width=4)

    # Blue header bar
    draw.rectangle((0, 0, W, 100), fill=(42, 86, 160))
    header_text = f"{username} | {description}"
    tw, _ = draw.textsize(header_text, font=font_header)
    draw.text(((W - tw) / 2, 30), header_text, fill="white", font=font_header)

    # Subheader watermark text
    watermark_text = "CITY OF LAKEVIEW • DMV • OFFICIAL USE ONLY  " * 4
    draw.text((30, 110), watermark_text[:95], fill=(90, 110, 150), font=font_small)

    # Avatar image
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

    # Labels and info
    base_x = 340
    y = 170
    spacing = 42
    field_color = (30, 30, 40)

    draw.text((base_x, y), username, fill=field_color, font=font_bold)
    y += spacing + 10
    draw.text((base_x, y), "Full Name:", fill=field_color, font=font_text)
    draw.text((base_x + 160, y), username, fill=field_color, font=font_text)
    y += spacing
    draw.text((base_x, y), "DOB:", fill=field_color, font=font_text)
    draw.text((base_x + 160, y), "N/A", fill=field_color, font=font_text)
    y += spacing
    draw.text((base_x, y), "Address:", fill=field_color, font=font_text)
    draw.text((base_x + 160, y), "N/A", fill=field_color, font=font_text)
    y += spacing
    draw.text((base_x, y), "Eye Color:", fill=field_color, font=font_text)
    draw.text((base_x + 160, y), "N/A", fill=field_color, font=font_text)
    y += spacing
    draw.text((base_x, y), "Height:", fill=field_color, font=font_text)
    draw.text((base_x + 160, y), "N/A", fill=field_color, font=font_text)
    y += spacing
    draw.text((base_x, y), "License #:", fill=field_color, font=font_text)
    draw.text((base_x + 160, y), lic_num, fill=field_color, font=font_text)

    # DMV Seal (bottom-right)
    cx, cy = 850, 500
    draw.ellipse((cx, cy, cx + 120, cy + 120), outline=(60, 90, 180), width=4)
    draw.text((cx + 38, cy + 45), "DMV", fill=(60, 90, 180), font=font_bold)

    # Notes section
    draw.rounded_rectangle((40, 460, 960, 610), radius=20, outline=(150, 160, 180), width=2, fill=(240, 243, 250))
    draw.text((60, 470), "Notes", fill=(60, 90, 180), font=font_bold)
    draw.text((760, 470), "Issued:", fill=field_color, font=font_text)
    draw.text((855, 470), issued.strftime("%Y-%m-%d"), fill=field_color, font=font_text)
    draw.text((760, 510), "Expires:", fill=field_color, font=font_text)
    draw.text((855, 510), expires.strftime("%Y-%m-%d"), fill=field_color, font=font_text)
    draw.text((700, 580), "Lakeview City Roleplay", fill=(60, 90, 180), font=font_small)

    # Footer DMV authority text
    auth_text = "License Sustained by Department of Motor Vehicles"
    draw.text((base_x, 440), auth_text, fill=(40, 80, 180), font=font_small)

    # Export to memory
    out = io.BytesIO()
    img.save(out, format="PNG")
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
