from __future__ import annotations

# --- stdlib ---
import os, io
from datetime import datetime, timedelta
from threading import Thread
import math

# --- third-party ---
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py ---
import discord
from discord.ext import commands


# =======================
# TOKEN / DISCORD SETUP
# =======================

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



# ======================
# FONT LOADING HANDLER
# ======================

def load_font(size: int, bold: bool = False):
    candidates = []

    if bold:
        candidates += [
            "arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates += [
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass

    return ImageFont.load_default()



# =================================
# LICENSE CARD IMAGE GENERATOR
# =================================

def create_license_image(
    username,
    avatar_bytes,
    display_name,
    roleplay_name,
    age,
    address,
    eye_color,
    height,
    issued,
    expires,
    lic_num,
):

    W, H = 820, 520

    # ================================
    # CARD BASE WITH FULL CURVED SHAPE
    # ================================
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Entire card rounded (top too)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=70, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    base.putalpha(mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    # ========================
    # BACKGROUND GRADIENT + WAVES
    # ========================
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)

    for y in range(H):
        ratio = y / H
        r = int(150 + 40 * ratio)
        g = int(180 + 50 * ratio)
        b = int(220 + 20 * ratio)
        bgd.line((0, y, W, y), fill=(r, g, b, 255))

    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)

    for x in range(0, W, 40):
        for y in range(0, H, 40):
            wd.arc((x, y, x + 80, y + 80), 0, 180, fill=(255, 255, 255, 25), width=2)

    wave = wave.filter(ImageFilter.GaussianBlur(1.5))
    bg.alpha_composite(wave)

    bg.putalpha(mask)
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    # ========================
    # HEADER BAR
    # ========================
    header = Image.new("RGBA", (W, 95), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))

    # Clip header to curved mask top
    header.putalpha(mask.crop((0, 0, W, 95)))
    card.alpha_composite(header, (0, 0))

    title_font = load_font(42, bold=True)
    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 25), title, fill="white", font=title_font)

    # ========================
    # DISPLAY NAME (CENTERED ABOVE AVATAR)
    # ========================
    disp_font = load_font(30, bold=True)
    disp_w = draw.textlength(display_name, font=disp_font)
    draw.text((150 - disp_w / 2, 110), display_name, fill=(30, 30, 30), font=disp_font)

    # ========================
    # AVATAR
    # ========================
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))

        m2 = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(m2).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        av.putalpha(m2)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58, 153))
        card.alpha_composite(av, (50, 145))
    except:
        pass

    # ========================
    # TEXT SECTIONS
    # ========================
    section_font = load_font(24, bold=True)
    label = load_font(22, bold=True)
    value = load_font(22)

    blue = (50, 110, 200)
    grey1 = (40, 40, 40)
    grey2 = (75, 75, 75)

    # ========================
    # IDENTITY (moved left 20px)
    # ========================
    ix = 280
    iy = 150

    draw.text((ix, iy), "IDENTITY", font=section_font, fill=blue)
    draw.line((ix, iy + 34, ix + 240, iy + 34), fill=blue, width=3)

    iy += 55
    draw.text((ix, iy), "Name:", font=label, fill=grey1)
    draw.text((ix + 110, iy), roleplay_name or username, font=value, fill=grey2)

    iy += 32
    draw.text((ix, iy), "Age:", font=label, fill=grey1)
    draw.text((ix + 110, iy), age, font=value, fill=grey2)

    iy += 32
    draw.text((ix, iy), "Address:", font=label, fill=grey1)
    draw.text((ix + 110, iy), address, font=value, fill=grey2)

    # ========================
    # PHYSICAL
    # ========================
    px = 550
    py = 150

    draw.text((px, py), "PHYSICAL", font=section_font, fill=blue)
    draw.line((px, py + 34, px + 240, py + 34), fill=blue, width=3)

    py += 55
    draw.text((px, py), "Eye Color:", font=label, fill=grey1)
    draw.text((px + 130, py), eye_color, font=value, fill=grey2)

    py += 32
    draw.text((px, py), "Height:", font=label, fill=grey1)
    draw.text((px + 130, py), height, font=value, fill=grey2)

    # ========================
    # DMV BOX
    # ========================
    BOX_Y = 360
    BOX_H = 140

    box = Image.new("RGBA", (W - 80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)

    bd.rounded_rectangle(
        (0, 0, W - 80, BOX_H),
        radius=35,
        fill=(200, 220, 255, 100),
        outline=(80, 140, 255, 180),
        width=3
    )

    card.alpha_composite(box, (40, BOX_Y))
    draw = ImageDraw.Draw(card)

    draw.text((60, BOX_Y + 15), "DMV INFO", font=section_font, fill=blue)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue, width=3)

    y2 = BOX_Y + 60

    draw.text((60, y2), "License Class:", font=label, fill=grey1)
    draw.text((215, y2), "Standard", font=value, fill=grey2)

    y2 += 32
    draw.text((60, y2), "Issued:", font=label, fill=grey1)
    draw.text((150, y2), issued.strftime('%Y-%m-%d'), font=value, fill=grey2)

    draw.text((330, y2), "Expires:", font=label, fill=grey1)
    draw.text((430, y2), expires.strftime('%Y-%m-%d'), font=value, fill=grey2)

    # ========================
    # STAR SEAL (8-point)
    # ========================
    seal = Image.new("RGBA", (95, 95), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal)

    cx, cy = 48, 48
    R1 = 46
    R2 = 20

    pts = []
    for i in range(16):
        ang = math.radians(i * 22.5)
        r = R1 if i % 2 == 0 else R2
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

    sd.polygon(pts, fill=(40, 90, 180), outline="white", width=3)
    seal = seal.filter(ImageFilter.GaussianBlur(0.8))

    card.alpha_composite(seal, (W - 150, BOX_Y + 15))

    # EXPORT
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()



# ======================
# DISCORD SENDER
# ======================

async def send_license_to_discord(img_data, filename, discord_id):
    await bot.wait_until_ready()
    file = discord.File(io.BytesIO(img_data), filename=filename)

    channel = bot.get_channel(1436890841703645285)
    if channel:
        embed = discord.Embed(
            title="Lakeview City Roleplay Driver’s License",
            color=0x757575
        )
        embed.set_image(url=f"attachment://{filename}")
        await channel.send(
            content=f"<@{discord_id}> Your license has been issued!",
            embed=embed,
            file=file
        )



# ======================
# FLASK API
# ======================

app = Flask(__name__)

@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        username = data.get("roblox_username")
        display = data.get("roblox_display")
        avatar = data.get("roblox_avatar")
        roleplay = data.get("roleplay_name")
        age = data.get("age")
        addr = data.get("address")
        eye = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")

        if not username or not avatar:
            return jsonify({"status": "error", "message": "Missing username/avatar"}), 400

        avatar_bytes = requests.get(avatar).content

        issued = datetime.utcnow()
        expires = issued + timedelta(days=150)

        img = create_license_image(
            username,
            avatar_bytes,
            display,
            roleplay,
            age,
            addr,
            eye,
            height,
            issued,
            expires,
            username
        )

        bot.loop.create_task(
            send_license_to_discord(img, f"{username}_license.png", discord_id)
        )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500



# ======================
# BOT READY
# ======================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")



# ======================
# RUN EVERYTHING
# ======================

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
