from __future__ import annotations

# --- stdlib
import os, io, json, asyncio
from datetime import datetime
from threading import Thread

# --- third-party
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py
import discord
from discord.ext import commands

# ========= TOKEN & CONFIG =========
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found!")

PREFIX = "?"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ---------- FONT LOADER ----------
def load_font(size: int, bold: bool = False):
    """Loads a clean sans-serif font, fallback safe."""
    try:
        if bold:
            return ImageFont.truetype("arialbd.ttf", size)
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

# ---------- LICENSE IMAGE ----------
def create_license_image(
    username, avatar_bytes, roleplay_name, age,
    address, eye_color, height, issued, expires, lic_num
):
    """Creates an ERLC-style Lakeview City Driver License"""

    W, H = 820, 520
    img = Image.new("RGB", (W, H), (245, 245, 245))
    draw = ImageDraw.Draw(img)

    # COLORS
    grey_dark = (40, 40, 40)
    grey_mid  = (70, 70, 70)
    blue_accent = (50, 110, 200)
    dmv_gold = (220, 180, 80)

    # FONTS
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22, bold=False)
    small_font = load_font(16, bold=False)

    # Rounded card
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=34, fill=255)
    card = Image.new("RGB", (W, H), (255, 255, 255))
    img.paste(card, (0, 0), mask)

    # License-themed Pattern Background
    pat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pat)
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            pdraw.rectangle(
                (x, y, x+18, y+18),
                fill=(220, 225, 235, 70)
            )
    img = Image.alpha_composite(img.convert("RGBA"), pat)

    # Dark "LAKEVIEW" WATERMARK
    wm_text = "LAKEVIEW"
    wm_font = load_font(130, bold=True)
    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    tw = wdraw.textlength(wm_text, font=wm_font)
    temp = Image.new("RGBA", (int(tw)+40, 160), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(temp)
    tdraw.text((20, 0), wm_text, font=wm_font, fill=(110, 110, 110, 55))
    temp = temp.rotate(33, expand=True, resample=Image.BICUBIC)
    temp = temp.filter(ImageFilter.GaussianBlur(1.4))
    watermark.paste(temp, (int(W/2 - temp.width/2), int(H/2 - temp.height/2)), temp)
    img = Image.alpha_composite(img, watermark)

    # HEADER
    header_text = "Lakeview City • Driver’s License"
    tw = draw.textlength(header_text, font=title_font)
    draw.text(((W - tw) / 2, 20), header_text, fill=grey_dark, font=title_font)

    # LEFT-SIDE AVATAR
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((200, 200))
            m = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, 200, 200), radius=26, fill=255)
            avatar.putalpha(m)
            img.paste(avatar, (45, 130), avatar)
        except Exception as e:
            print("[Avatar Error]", e)

    # LEFT COLUMN TEXT
    left_x = 280
    y = 130
    spacing = 36

    # Username
    draw.text((left_x, y), f"@{username}", fill=blue_accent, font=label_font)
    y += spacing

    # Name
    draw.text((left_x, y), "Name:", fill=grey_dark, font=label_font)
    draw.text((left_x + 120, y), roleplay_name or username, fill=grey_mid, font=value_font)
    y += spacing

    # Age
    draw.text((left_x, y), "Age:", fill=grey_dark, font=label_font)
    draw.text((left_x + 120, y), age or "N/A", fill=grey_mid, font=value_font)
    y += spacing

    # Address
    draw.text((left_x, y), "Address:", fill=grey_dark, font=label_font)
    draw.text((left_x + 120, y), address or "N/A", fill=grey_mid, font=value_font)

    # RIGHT COLUMN
    rx = 280
    ry = 300

    draw.text((rx, ry), "Eye Color:", fill=grey_dark, font=label_font)
    draw.text((rx + 140, ry), eye_color or "N/A", fill=grey_mid, font=value_font)

    ry += spacing
    draw.text((rx, ry), "Height:", fill=grey_dark, font=label_font)
    draw.text((rx + 140, ry), height or "N/A", fill=grey_mid, font=value_font)

    # DMV INFO (BOTTOM BAR)
    info_y = 380
    draw.line((40, info_y, W - 40, info_y), fill=(180, 180, 180), width=2)

    info_y += 20
    draw.text((50, info_y), f"License: {lic_num}", fill=grey_dark, font=label_font)
    draw.text((330, info_y), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)
    draw.text((570, info_y), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)

    # DMV NOTES
    notes_y = 440
    draw.text((50, notes_y), "This license is property of the Lakeview City DMV.", font=small_font, fill=grey_mid)
    draw.text((50, notes_y+22), "Tampering, duplication, or misuse is prohibited by law.", font=small_font, fill=grey_mid)

    # DMV GOLD SEAL (RIGHT SIDE)
    seal = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    sdraw.ellipse((0, 0, 160, 160), outline=(220, 180, 80, 255), width=5)
    sdraw.ellipse((20, 20, 140, 140), outline=(220, 180, 80, 160), width=2)
    sdraw.text((45, 65), "Lakeview\nCity DMV\nCertified", fill=dmv_gold, font=small_font, align="center")
    seal = seal.filter(ImageFilter.GaussianBlur(0.8))
    img.paste(seal, (W - 200, 170), seal)

    # HOLOGRAPHIC OVERLAY
    holo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(holo)

    for i in range(H):
        color = (255, 220 - int(25 * (i/H)), 120, int(25 + 18*(i/H)))  # warm golden
        hdraw.line((0, i, W, i), fill=color)

    holo = holo.filter(ImageFilter.GaussianBlur(7))
    holo.putalpha(50)  # // reduce opacity
    img = Image.alpha_composite(img, holo)

    # EXPORT
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# ---------- FLASK ----------
app = Flask(__name__)

@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")
        roleplay_name = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye_color = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")

        if not username or not avatar_url:
            return jsonify({"status": "error"}), 400

        avatar_bytes = requests.get(avatar_url).content

        img_data = create_license_image(
            username, avatar_bytes, roleplay_name, age,
            address, eye_color, height,
            datetime.utcnow(), datetime.utcnow(),
            "AUTO"
        )

        async def send_license():
            await bot.wait_until_ready()

            file = discord.File(io.BytesIO(img_data), filename=f"{username}_license.png")

            # Channel send
            channel = bot.get_channel(1436890841703645285)
            if channel:
                embed = discord.Embed(
                    title="Lakeview City Roleplay Driver’s License",
                    color=0x757575
                )
                embed.set_image(url=f"attachment://{username}_license.png")
                await channel.send(content=f"<@{discord_id}> Your license has been issued.", embed=embed, file=file)

            # DM send
            if discord_id:
                user = bot.get_user(int(discord_id))
                if user:
                    dm = discord.Embed(
                        title="Your Lakeview City Driver’s License",
                        color=0x757575
                    )
                    dm.set_image(url=f"attachment://{username}_license.png")
                    await user.send(embed=dm, file=discord.File(io.BytesIO(img_data), filename=f"{username}_license.png"))

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("[Webhook Error]", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- COMMANDS ----------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency*1000)}ms`")

# ---------- BOT READY ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ---------- RUN ----------
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Starting Flask...")
    app.run(host="0.0.0.0", port=8080)
