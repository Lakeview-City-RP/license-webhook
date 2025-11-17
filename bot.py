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
    candidates = []

    if bold:
        candidates += [
            "arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]
    else:
        candidates += [
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]

    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass

    return ImageFont.load_default()


# =================================
# LICENSE CARD IMAGE GENERATOR
# =================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520

    # Main card with curved mask
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
    mesh_color = (200, 200, 215, 40)
    box_bg = (200, 220, 255, 100)
    box_border = (80, 140, 255, 170)

    # MATTE BLUE DIAMOND COLORS
    matte_blue = (40, 70, 150)        # fill color
    matte_border = (255, 255, 255)    # white border
    matte_text = (220, 230, 255)      # light blue text

    # Fonts
    title_font = load_font(42, bold=True)
    section_font = load_font(24, bold=True)
    bold_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(15)
    wm_font = load_font(110, bold=True)

    # ======================
    # HEADER BAR (SAFE)
    # ======================
    header = Image.new("RGBA", (W, 95), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)
    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))
    card.paste(header, (0, 0), header)

    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 25), title, fill="white", font=title_font)

    # ======================
    # BACKGROUND MESH INSIDE MASK
    # ======================
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)
    spacing = 34

    for y in range(120, H, spacing):
        for x in range(0, W, spacing):
            md.line((x, y, x + spacing//2, y + spacing//2),
                    fill=mesh_color, width=2)
            md.line((x + spacing//2, y, x, y + spacing//2),
                    fill=mesh_color, width=2)

    mesh = mesh.filter(ImageFilter.GaussianBlur(0.7))
    mesh.putalpha(mask)
    card = Image.alpha_composite(card, mesh)
    draw = ImageDraw.Draw(card)

    # ======================
    # WATERMARK
    # ======================
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wmd = ImageDraw.Draw(wm)

    wm_text = "LAKEVIEW"
    tw = wmd.textlength(wm_text, font=wm_font)

    wimg = Image.new("RGBA", (int(tw) + 40, 200), (0, 0, 0, 0))
    dd = ImageDraw.Draw(wimg)
    dd.text((20, 0), wm_text, font=wm_font, fill=(150, 150, 150, 30))

    wimg = wimg.rotate(28, expand=True)
    wimg = wimg.filter(ImageFilter.GaussianBlur(1.2))

    wm.paste(wimg, (W//2 - wimg.width//2, H//3), wimg)
    wm.putalpha(mask)
    card = Image.alpha_composite(card, wm)
    draw = ImageDraw.Draw(card)

    # ======================
    # AVATAR
    # ======================
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))

        av_mask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(av_mask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        av.putalpha(av_mask)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.paste(shadow, (58, 153), shadow)
        card.paste(av, (50, 145), av)
    except:
        pass

    # ======================
    # IDENTITY + PHYSICAL
    # ======================
    ix = 300
    iy = 150

    draw.text((ix, iy), "IDENTITY", font=section_font, fill=blue_accent)
    draw.line((ix, iy+34, ix+240, iy+34), fill=blue_accent, width=3)

    px = 550
    py = 150

    draw.text((px, py), "PHYSICAL", font=section_font, fill=blue_accent)
    draw.line((px, py+34, px+240, py+34), fill=blue_accent, width=3)

    # Identity
    iy += 55
    draw.text((ix, iy), "Name:", font=bold_font, fill=grey_dark)
    draw.text((ix+120, iy), roleplay_name or username, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Age:", font=bold_font, fill=grey_dark)
    draw.text((ix+120, iy), age, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Address:", font=bold_font, fill=grey_dark)
    draw.text((ix+120, iy), address, font=value_font, fill=grey_mid)

    # Physical
    py += 55
    draw.text((px, py), "Eye Color:", font=bold_font, fill=grey_dark)
    draw.text((px+140, py), eye_color, font=value_font, fill=grey_mid)
    py += 32

    draw.text((px, py), "Height:", font=bold_font, fill=grey_dark)
    draw.text((px+140, py), height, font=value_font, fill=grey_mid)

    # ======================
    # DMV INFO BOX (lower + fixed)
    # ======================
    BOX_Y = 370  # Lowered 30px from 340
    BOX_H = 130

    box = Image.new("RGBA", (W-80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle(
        (0, 0, W-80, BOX_H),
        radius=35,
        fill=box_bg,
        outline=box_border,
        width=3
    )

    card.paste(box, (40, BOX_Y), box)

    draw.text((60, BOX_Y+15), "DMV INFO", font=section_font, fill=blue_accent)
    draw.line((60, BOX_Y+47, 300, BOX_Y+47), fill=blue_accent, width=3)

    y2 = BOX_Y + 60
    draw.text((60, y2), "License Class:", font=bold_font, fill=grey_dark)
    draw.text((215, y2), "Standard", font=value_font, fill=grey_mid)
    y2 += 30

    draw.text((60, y2), "Issued:", font=bold_font, fill=grey_dark)
    draw.text((215, y2), issued.strftime("%Y-%m-%d"), font=value_font, fill=grey_mid)
    y2 += 30

    draw.text((60, y2), "Expires:", font=bold_font, fill=grey_dark)
    draw.text((215, y2), expires.strftime("%Y-%m-%d"), font=value_font, fill=grey_mid)

    # ======================
    # MATTE BLUE DIAMOND BADGE (95x95)
    # ======================
    DIAM = 95
    diamond = Image.new("RGBA", (DIAM, DIAM), (0, 0, 0, 0))
    d = ImageDraw.Draw(diamond)

    points = [
        (DIAM//2, 0),
        (DIAM, DIAM//2),
        (DIAM//2, DIAM),
        (0, DIAM//2)
    ]

    d.polygon(points, fill=matte_blue, outline=matte_border, width=4)

    # centered text
    d.text((DIAM//2 - 27, DIAM//2 - 18), "DMV\nCERTIFIED",
           font=small_font, fill=matte_text, align="center")

    card.paste(diamond, (W - 150, BOX_Y + 10), diamond)

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
        avatar_url = data.get("roblox_avatar")
        roleplay = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")

        if not username or not avatar_url:
            return jsonify({"status": "error", "message": "Missing fields"}), 400

        avatar_bytes = requests.get(avatar_url).content

        issued = datetime.utcnow()
        expires = issued + timedelta(days=150)

        img = create_license_image(
            username, avatar_bytes, roleplay, age, address,
            eye, height, issued, expires, username
        )

        bot.loop.create_task(send_license_to_discord(
            img, f"{username}_license.png", discord_id))

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
