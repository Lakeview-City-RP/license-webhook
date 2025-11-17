from __future__ import annotations

# --- stdlib ---
import os, io
from datetime import datetime, timedelta
from threading import Thread

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
    paths = [
        ("arialbd.ttf" if bold else "arial.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    ]

    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            continue

    return ImageFont.load_default()


# =================================
# LICENSE CARD IMAGE GENERATOR
# =================================

def create_license_image(username, display_name, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520

    # BASE CARD WITH CURVED CORNERS
    card = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=70, fill=255)
    card.putalpha(mask)
    draw = ImageDraw.Draw(card)

    # Colors
    header_blue = (35, 70, 140)
    grey_dark = (40, 40, 40)
    grey_mid = (75, 75, 75)
    blue_accent = (50, 110, 200)
    watermark_color = (150, 150, 150, 30)
    badge_blue = (40, 70, 160)
    badge_border = (255, 255, 255)

    # Fonts
    title_font = load_font(42, bold=True)
    section_font = load_font(24, bold=True)
    bold_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(15, bold=True)
    watermark_font = load_font(110, bold=True)

    # HEADER BAR
    header = Image.new("RGBA", (W, 95))
    hd = ImageDraw.Draw(header)
    for i in range(95):
        shade = int(35 + (65 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))
    card.alpha_composite(header, (0, 0))

    # TITLE
    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 25), title, fill="white", font=title_font)

    # BACKGROUND PATTERN (SAFE VERSION, stays inside)
    pattern = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pattern)
    for y in range(100, H, 45):
        for x in range(0, W, 45):
            pd.text((x, y), "◦", fill=(180, 180, 180, 40), font=value_font)
    card.alpha_composite(pattern)

    # WATERMARK
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wmd = ImageDraw.Draw(wm)
    wm_text = "LAKEVIEW"
    t_w = wmd.textlength(wm_text, font=watermark_font)
    w_temp = Image.new("RGBA", (int(t_w) + 40, 200), (0, 0, 0, 0))
    td = ImageDraw.Draw(w_temp)
    td.text((20, 0), wm_text, font=watermark_font, fill=watermark_color)
    w_temp = w_temp.rotate(28, expand=True)
    wm.alpha_composite(w_temp, (W // 2 - w_temp.width // 2, H // 3))
    card.alpha_composite(wm)

    # AVATAR
    av_x, av_y = 50, 145
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))
        mask2 = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(mask2).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        av.putalpha(mask2)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (av_x + 8, av_y + 8))
        card.alpha_composite(av, (av_x, av_y))
    except:
        pass

    # DISPLAY NAME ABOVE PHOTO
    if display_name:
        dn_w = draw.textlength(display_name, font=bold_font)
        draw.text((av_x + 100 - dn_w/2, av_y - 35), display_name, fill=grey_dark, font=bold_font)

    # TEXT SECTIONS
    ix, iy = 300, 150
    draw.text((ix, iy), "IDENTITY", font=section_font, fill=blue_accent)
    draw.line((ix, iy + 32, ix + 240, iy + 32), fill=blue_accent, width=3)

    px, py = 550, 150
    draw.text((px, py), "PHYSICAL", font=section_font, fill=blue_accent)
    draw.line((px, py + 32, px + 240, py + 32), fill=blue_accent, width=3)

    iy += 55
    draw.text((ix, iy), "Name:", font=bold_font, fill=grey_dark)
    draw.text((ix + 120, iy), roleplay_name or username, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Age:", font=bold_font, fill=grey_dark)
    draw.text((ix + 120, iy), age, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Address:", font=bold_font, fill=grey_dark)
    draw.text((ix + 120, iy), address, font=value_font, fill=grey_mid)

    py += 55
    draw.text((px, py), "Eye Color:", font=bold_font, fill=grey_dark)
    draw.text((px + 140, py), eye_color, font=value_font, fill=grey_mid)
    py += 32

    draw.text((px, py), "Height:", font=bold_font, fill=grey_dark)
    draw.text((px + 140, py), height, font=value_font, fill=grey_mid)

    # DMV INFO BOX (lowered)
    BOX_Y = 360
    BOX_H = 140

    box = Image.new("RGBA", (W - 80, BOX_H))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle((0, 0, W - 80, BOX_H), radius=35,
                         fill=(200, 220, 255, 100),
                         outline=(80, 140, 255, 180), width=3)

    card.alpha_composite(box, (40, BOX_Y))

    draw.text((60, BOX_Y + 15), "DMV INFO", font=section_font, fill=blue_accent)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue_accent, width=3)

    y2 = BOX_Y + 60
    draw.text((60, y2), "License Class:", font=bold_font, fill=grey_dark)
    draw.text((215, y2), "Standard", font=value_font, fill=grey_mid)
    y2 += 30

    draw.text((60, y2), "Issued:", font=bold_font, fill=grey_dark)
    draw.text((215, y2), issued.strftime("%Y-%m-%d"), font=value_font, fill=grey_mid)
    y2 += 30

    draw.text((60, y2), "Expires:", font=bold_font, fill=grey_dark)
    draw.text((215, y2), expires.strftime("%Y-%m-%d"), font=value_font, fill=grey_mid)

    # DMV BADGE (95x95)
    badge = Image.new("RGBA", (95, 95), (0, 0, 0, 0))
    bdg = ImageDraw.Draw(badge)

    points = [(47, 0), (95, 47), (47, 95), (0, 47)]
    bdg.polygon(points, fill=badge_blue, outline=badge_border, width=4)

    bdg.text((27, 33), "DMV\nCERTIFIED", fill="white", font=small_font, align="center")

    card.alpha_composite(badge, (W - 135, BOX_Y + 12))

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
        embed = discord.Embed(title="Lakeview City Roleplay Driver’s License", color=0x757575)
        embed.set_image(url=f"attachment://{filename}")
        await channel.send(content=f"<@{discord_id}> Your license has been issued!",
                           embed=embed, file=file)


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
        display_name = data.get("roblox_display")
        avatar_url = data.get("roblox_avatar")
        roleplay = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")

        avatar_bytes = requests.get(avatar_url).content

        issued = datetime.utcnow()
        expires = issued + timedelta(days=150)

        img = create_license_image(
            username, display_name, avatar_bytes, roleplay, age,
            address, eye, height, issued, expires, username
        )

        bot.loop.create_task(send_license_to_discord(
            img, f"{username}_license.png", discord_id
        ))

        return jsonify({"status": "ok"}), 200

    except Exception as e:
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
