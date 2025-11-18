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


# ============================================================
# TOKEN / DISCORD SETUP
# ============================================================

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


# ============================================================
# FONT LOADING
# ============================================================

def load_font(size: int, bold: bool = False):
    files = [
        ("arialbd.ttf" if bold else "arial.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for f in files:
        try:
            return ImageFont.truetype(f, size)
        except:
            pass
    return ImageFont.load_default()


# ============================================================
# LICENSE IMAGE GENERATOR (UPDATED, NO CRASH)
# ============================================================

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

    # Safety: make sure text values are strings
    username_str = str(username) if username is not None else ""
    roleplay_name_str = str(roleplay_name) if roleplay_name is not None else username_str
    age_str = str(age) if age is not None else ""
    address_str = str(address) if address is not None else ""
    eye_color_str = str(eye_color) if eye_color is not None else ""
    height_str = str(height) if height is not None else ""

    # Full card base with rounded edges
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(full_mask).rounded_rectangle((0, 0, W, H), 120, fill=255)
    base = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    base.putalpha(full_mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    # Background gradient
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    for y in range(H):
        ratio = y / H
        r = int(150 + 40 * ratio)
        g = int(180 + 50 * ratio)
        b = int(220 + 20 * ratio)
        bgd.line((0, y, W, y), fill=(r, g, b, 255))

    # Light wave pattern
    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)
    for x in range(0, W, 40):
        for y in range(0, H, 40):
            wd.arc((x, y, x + 80, y + 80), 0, 180, fill=(255, 255, 255, 25), width=2)
    wave = wave.filter(ImageFilter.GaussianBlur(1.4))
    bg.alpha_composite(wave)

    bg.putalpha(full_mask)
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    # ============================================================
    # HEADER — CURVED WITH CARD, BUT SAFE
    # ============================================================

    HEADER_H = 95
    header = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))

    # Blue gradient header
    hd = ImageDraw.Draw(header)
    for i in range(HEADER_H):
        shade = int(35 + (60 - 35) * (i / HEADER_H))
        hd.line((0, i, W, i), fill=(shade, 70, 160))

    # IMPORTANT FIX:
    # Use the TOP SLICE of the full rounded card mask
    # This guarantees the header curve matches the license AND never crashes.
    header_mask = full_mask.crop((0, 0, W, HEADER_H))
    header.putalpha(header_mask)

    # Overlay header at the top
    card.alpha_composite(header, (0, 0))

    # Title centered
    title_font = load_font(42, bold=True)
    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 24), title, fill="white", font=title_font)

    # ============================================================
    # AVATAR
    # ============================================================

    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))

        mask2 = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(mask2).rounded_rectangle((0, 0, 200, 200), 42, fill=255)
        av.putalpha(mask2)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58, 158))
        card.alpha_composite(av, (50, 150))
    except Exception:
        # If avatar fails for any reason, don't crash the whole image.
        pass

    # ============================================================
    # TEXT STYLES
    # ============================================================

    section = load_font(24, bold=True)
    bold = load_font(22, bold=True)
    normal = load_font(22)
    blue = (50, 110, 200)
    grey = (35, 35, 35)

    # ============================================================
    # IDENTITY SECTION
    # ============================================================

    ix = 290
    iy = 160
    draw.text((ix, iy), "IDENTITY", font=section, fill=blue)
    draw.line((ix, iy + 34, ix + 250, iy + 34), fill=blue, width=3)

    iy += 55

    def write_pair(x, y, label, value):
        value_str = "" if value is None else str(value)
        lw = draw.textlength(label, font=bold)
        draw.text((x, y), label, font=bold, fill=grey)
        draw.text((x + lw + 10, y), value_str, font=normal, fill=grey)

    write_pair(ix, iy, "Name:", roleplay_name_str)
    write_pair(ix, iy + 34, "Age:", age_str)
    write_pair(ix, iy + 68, "Address:", address_str)

    # ============================================================
    # PHYSICAL SECTION
    # ============================================================

    px = 550
    py = 160
    draw.text((px, py), "PHYSICAL", font=section, fill=blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)

    py += 55

    write_pair(px, py, "Eye Color:", eye_color_str)
    write_pair(px, py + 34, "Height:", height_str)

    # ============================================================
    # DMV BOX
    # ============================================================

    BOX_Y = 360
    BOX_H = 140

    box = Image.new("RGBA", (W - 80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)

    bd.rounded_rectangle(
        (0, 0, W - 80, BOX_H),
        radius=45,
        fill=(200, 220, 255, 90),
        outline=(80, 140, 255, 180),
        width=3,
    )
    card.alpha_composite(box, (40, BOX_Y))
    draw = ImageDraw.Draw(card)

    # DMV TITLE
    draw.text((60, BOX_Y + 15), "DMV INFO", font=section, fill=blue)

    # LINE
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue, width=3)

    # ============================================================
    # CENTERED BOLD USERNAME IN DMV BOX
    # ============================================================

    username_font = load_font(24, bold=True)
    uname_w = draw.textlength(username_str, font=username_font)

    box_center_x = 40 + (W - 80) // 2
    name_x = box_center_x - (uname_w / 2)
    name_y = BOX_Y + 15  # aligned w/ DMV INFO

    draw.text((name_x, name_y), username_str, font=username_font, fill=grey)

    # ============================================================
    # DMV DETAILS
    # ============================================================

    y2 = BOX_Y + 65
    draw.text((60, y2), "License Class:", font=bold, fill=grey)
    draw.text((245, y2), "Standard", font=normal, fill=grey)

    y2 += 38
    draw.text((60, y2), "Issued:", font=bold, fill=grey)
    draw.text((150, y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    draw.text((330, y2), "Expires:", font=bold, fill=grey)
    draw.text((430, y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    # Seal
    seal = Image.new("RGBA", (95, 95), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal)
    cx, cy = 48, 48
    R1, R2 = 44, 19
    pts = []
    for i in range(16):
        ang = math.radians(i * 22.5)
        r = R1 if i % 2 == 0 else R2
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    sd.polygon(pts, fill=(40, 90, 180), outline="white", width=3)
    seal = seal.filter(ImageFilter.GaussianBlur(0.8))

    card.alpha_composite(seal, (W - 150, BOX_Y + 10))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ============================================================
# SEND TO DISCORD
# ============================================================

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
            file=file,
        )


# ============================================================
# FLASK API
# ============================================================

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
            username,
        )

        bot.loop.create_task(
            send_license_to_discord(img, f"{username}_license.png", discord_id)
        )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print("Slash sync error:", e)


async def setup_hook():
    await bot.load_extension("cogs.economy")

bot.setup_hook = setup_hook


# ============================================================
# RUN BOT + FLASK
# ============================================================

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
