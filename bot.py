from __future__ import annotations

# --- stdlib ---
import os
import io
import math
from datetime import datetime, timedelta
from threading import Thread
import aiosqlite


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
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for f in files:
        try:
            return ImageFont.truetype(f, size)
        except:
            pass
    return ImageFont.load_default()


# ============================================================
# LICENSE IMAGE GENERATOR (STANDARD + PROVISIONAL)
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
    license_type
):
    W, H = 820, 520

    # Coerce to strings
    username_str = str(username) if username else ""
    roleplay_name_str = str(roleplay_name) if roleplay_name else username_str
    age_str = str(age) if age else ""
    address_str = str(address) if address else ""
    eye_color_str = str(eye_color) if eye_color else ""
    height_str = str(height) if height else ""
    lic_num_str = str(lic_num)

    # Base rounded card
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(full_mask).rounded_rectangle((0, 0, W, H), 120, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    base.putalpha(full_mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    # =======================
    # Background gradient
    # =======================

    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)

    for y in range(H):
        ratio = y / H

        if license_type == "provisional":
            # Warm orange gradient
            r = int(255 - 30 * ratio)
            g = int(180 + 20 * ratio)
            b = int(80 - 30 * ratio)
        else:
            # Original blue gradient
            r = int(150 + 40 * ratio)
            g = int(180 + 50 * ratio)
            b = int(220 + 20 * ratio)

        bgd.line((0, y, W, y), fill=(r, g, b))

    # =======================
    # MESH (color depends on type)
    # =======================

    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)

    if license_type == "provisional":
        # Orange gradient-matching mesh
        mesh_color = (255, 180, 100, 45)
    else:
        mesh_color = (255, 255, 255, 40)

    for x in range(0, W, 40):
        for y in range(0, H, 40):
            wd.arc((x, y, x + 80, y + 80), 0, 180, fill=mesh_color, width=2)

    wave = wave.filter(ImageFilter.GaussianBlur(1.2))
    bg.alpha_composite(wave)

    bg.putalpha(full_mask)
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    # ============================================================
    # HEADER (Blue or Orange)
    # ============================================================

    HEADER_H = 95

    if license_type == "provisional":
        header_color_start = (225, 150, 30)
        header_color_end = (255, 185, 60)
        title_text = "LAKEVIEW PROVISIONAL LICENSE"
        title_font = load_font(33, bold=True)
    else:
        header_color_start = (35, 70, 160)
        header_color_end = (60, 100, 190)
        title_text = "LAKEVIEW CITY DRIVER LICENSE"
        title_font = load_font(39, bold=True)

    header = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(HEADER_H):
        r = int(header_color_start[0] + (header_color_end[0] - header_color_start[0]) * (i / HEADER_H))
        g = int(header_color_start[1] + (header_color_end[1] - header_color_start[1]) * (i / HEADER_H))
        b = int(header_color_start[2] + (header_color_end[2] - header_color_start[2]) * (i / HEADER_H))
        hd.line((0, i, W, i), fill=(r, g, b))

    header_mask = full_mask.crop((0, 0, W, HEADER_H))
    header.putalpha(header_mask)
    card.alpha_composite(header, (0, 0))

    tw = draw.textlength(title_text, font=title_font)
    draw.text(((W - tw) / 2, 24), title_text, fill="white", font=title_font)

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
    except:
        pass

    # ============================================================
    # TEXT STYLES
    # ============================================================

    section = load_font(24, bold=True)
    boldf = load_font(22, bold=True)
    normal = load_font(22)
    if license_type == "provisional":
        blue = (230, 140, 30)  # Orange section/header color
    else:
        blue = (50, 110, 200)

    grey = (35, 35, 35)

    # ============================================================
    # IDENTITY
    # ============================================================

    ix = 290
    iy = 160
    draw.text((ix, iy), "IDENTITY:", font=section, fill=blue)
    draw.line((ix, iy + 34, ix + 250, iy + 34), fill=blue, width=3)

    iy += 55

    def write_pair(x, y, label, value):
        lw = draw.textlength(label, font=boldf)
        draw.text((x, y), label, font=boldf, fill=grey)
        draw.text((x + lw + 10, y), value, font=normal, fill=grey)

    write_pair(ix, iy, "Name:", roleplay_name_str)
    write_pair(ix, iy + 34, "Age:", age_str)
    write_pair(ix, iy + 68, "Address:", address_str)

    # ============================================================
    # PHYSICAL
    # ============================================================

    px = 550
    py = 160
    draw.text((px, py), "PHYSICAL:", font=section, fill=blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)

    py += 55
    write_pair(px, py, "Eye Color:", eye_color_str)
    write_pair(px, py + 34, "Height:", height_str)

    # ============================================================
    # DMV BOX
    # ============================================================

    BOX_Y = 360
    BOX_H = 140

    # Colors (provisional = orange, standard = blue)
    if license_type == "provisional":
        fill_color = (255, 200, 150, 110)
        outline_color = (240, 150, 60, 200)
    else:
        fill_color = (200, 220, 255, 90)
        outline_color = (80, 140, 255, 180)

    # Create box
    box = Image.new("RGBA", (W - 80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)

    bd.rounded_rectangle(
        (0, 0, W - 80, BOX_H),
        radius=45,
        fill=fill_color,
        outline=outline_color,
        width=3,
    )

    card.alpha_composite(box, (40, BOX_Y))
    draw = ImageDraw.Draw(card)

    # DMV INFO label
    draw.text((60, BOX_Y + 15), "DMV INFO:", font=section, fill=blue)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue, width=3)

    username_font = load_font(24, bold=True)
    uname_w = draw.textlength(username_str, font=username_font)
    name_center = 40 + (W - 80) // 2 - uname_w // 2

    # ============================================================
    # DMV DETAILS
    # ============================================================

    if license_type == "provisional":
        class_label = "Provisional"
    else:
        class_label = "Standard"

    y2 = BOX_Y + 65
    draw.text((60, y2), "License Class:", font=boldf, fill=grey)
    draw.text((245, y2), class_label, font=normal, fill=grey)

    # LICENSE NUMBER (PLACED TO THE RIGHT OF CLASS)
    draw.text((430, y2), f"License #: {lic_num_str}", font=normal, fill=grey)

    y2 += 38
    draw.text((60, y2), "Issued:", font=boldf, fill=grey)
    draw.text((150, y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    draw.text((330, y2), "Expires:", font=boldf, fill=grey)
    draw.text((430, y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    # ============================================================
    # STAR SEAL
    # ============================================================

    seal = Image.new("RGBA", (95, 95), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal)
    cx, cy = 48, 48
    R1, R2 = 44, 19
    pts = []
    for i in range(16):
        ang = math.radians(i * 22.5)
        r = R1 if i % 2 == 0 else R2
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    if license_type == "provisional":
        seal_color = (255, 150, 40)  # bright orange
        outline_color = (255, 230, 180)  # soft light-orange outline
    else:
        seal_color = (40, 90, 180)
        outline_color = "white"

    sd.polygon(pts, fill=seal_color, outline=outline_color, width=3)

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
        embed = discord.Embed(color=0x757575)
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
        license_type = data.get("license_type", "standard").lower()
        lic_num = data.get("license_number", username)

        if not username or not avatar:
            return jsonify({"status": "error", "message": "Missing username/avatar"}), 400

        avatar_bytes = requests.get(avatar).content

        issued = datetime.utcnow()

        if license_type == "provisional":
            expires = issued + timedelta(days=3)
        else:
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
            lic_num,
            license_type
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
# SINGLE CORRECT SETUP HOOK
# ============================================================
import aiosqlite

async def setup_hook():
    # Create database BEFORE loading any extension that uses it
    bot.db = await aiosqlite.connect("workforce.db")

    # Load other cogs
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.erlc_application")
    await bot.load_extension("cogs.auto_giveaway")
    print("Cogs loaded")

bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced: {len(synced)}")
    except Exception as e:
        print("Slash sync error:", e)



# ============================================================
# RUN BOT + FLASK
# ============================================================

def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
