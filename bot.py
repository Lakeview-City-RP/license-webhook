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
    # --- CANVAS SIZE ---
    W, H = 820, 520

    # --- SAFE STRINGS ---
    username_str = str(username or "")
    roleplay_name_str = str(roleplay_name or username_str)
    age_str = str(age or "")
    addr_str = str(address or "")
    eye_str = str(eye_color or "")
    height_str = str(height or "")
    lic_num_str = str(lic_num or "")

    # --- BASE CARD ---
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(full_mask).rounded_rectangle((0, 0, W, H), 120, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    base.putalpha(full_mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    # ====================================================
    # BACKGROUND GRADIENT
    # ====================================================
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)

    for y in range(H):
        ratio = y / H

        if license_type == "provisional":
            r = int(255 - 50 * ratio)
            g = int(150 + 40 * ratio)
            b = int(60 - 40 * ratio)
        else:
            r = int(150 + 40 * ratio)
            g = int(180 + 50 * ratio)
            b = int(220 + 20 * ratio)

        r = min(255, max(0, r))
        g = min(255, max(0, g))
        b = min(255, max(0, b))

        bgd.line((0, y, W, y), fill=(r, g, b))

    # ====================================================
    # MESH / WAVE PATTERN
    # ====================================================
    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)

    mesh_color = (255, 180, 100, 45) if license_type == "provisional" else (255, 255, 255, 40)

    for x in range(0, W, 40):
        for y in range(0, H, 40):
            wd.arc((x, y, x + 80, y + 80), 0, 180, fill=mesh_color, width=2)

    wave = wave.filter(ImageFilter.GaussianBlur(1.2))
    bg.alpha_composite(wave)

    bg.putalpha(full_mask)
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    # ====================================================
    # HEADER BAR
    # ====================================================
    HEADER_H = 95

    if license_type == "provisional":
        header_color_start = (225, 140, 20)
        header_color_end   = (255, 200, 80)
        title_text = "LAKEVIEW PROVISIONAL LICENSE"
        title_font = load_font(35, bold=True)
    else:
        header_color_start = (35, 70, 160)
        header_color_end   = (60, 100, 190)
        title_text = "LAKEVIEW CITY DRIVER LICENSE"
        title_font = load_font(39, bold=True)

    header = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(HEADER_H):
        t = i / HEADER_H
        r = int(header_color_start[0] + (header_color_end[0] - header_color_start[0]) * t)
        g = int(header_color_start[1] + (header_color_end[1] - header_color_start[1]) * t)
        b = int(header_color_start[2] + (header_color_end[2] - header_color_start[2]) * t)
        hd.line((0, i, W, i), fill=(r, g, b))

    header.putalpha(full_mask.crop((0, 0, W, HEADER_H)))
    card.alpha_composite(header, (0, 0))

    # Title shadow + text
    tw = draw.textlength(title_text, font=title_font)
    draw.text((W/2 - tw/2 + 2, 26 + 2), title_text, fill=(0, 0, 0, 120), font=title_font)
    draw.text((W/2 - tw/2, 26), title_text, fill="white", font=title_font)

    # ====================================================
    # AVATAR
    # ====================================================
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))
        m = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, 200, 200), 42, fill=255)
        av.putalpha(m)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58, 158))
        card.alpha_composite(av, (50, 150))
    except:
        pass

    # ====================================================
    # TEXT COLORS & FONTS
    # ====================================================
    section = load_font(24, bold=True)
    boldf   = load_font(22, bold=True)
    normal  = load_font(22)

    blue = (160, 70, 20) if license_type == "provisional" else (50, 110, 200)
    grey = (35, 35, 35)

    # outline text helper
    def ot(x, y, txt, font, fill):
        for ox, oy in [(-1,0),(1,0),(0,-1),(0,1)]:
            draw.text((x+ox, y+oy), txt, font=font, fill=(0,0,0,120))
        draw.text((x, y), txt, font=font, fill=fill)

    # ====================================================
    # IDENTITY SECTION
    # ====================================================
    ix, iy = 290, 160
    ot(ix, iy, "IDENTITY:", section, blue)
    draw.line((ix, iy+34, ix+250, iy+34), fill=blue, width=3)

    iy += 55

    def wp(x, y, label, value):
        lw = draw.textlength(label, font=boldf)
        draw.text((x, y), label, font=boldf, fill=grey)
        draw.text((x + lw + 10, y), value, font=normal, fill=grey)

    wp(ix, iy, "Name:", roleplay_name_str)
    wp(ix, iy+34, "Age:", age_str)
    wp(ix, iy+68, "Address:", addr_str)

    # ====================================================
    # PHYSICAL SECTION
    # ====================================================
    px, py = 550, 160
    ot(px, py, "PHYSICAL:", section, blue)
    draw.line((px, py+34, px+250, py+34), fill=blue, width=3)

    py += 55
    wp(px, py, "Eye Color:", eye_str)
    wp(px, py+34, "Height:", height_str)

    # ====================================================
    # DMV INFO BOX
    # ====================================================
    BOX_Y, BOX_H = 360, 140

    if license_type == "provisional":
        fill_color    = (255, 190, 130, 130)
        outline_color = (180, 90, 20, 255)
    else:
        fill_color    = (200, 220, 255, 90)
        outline_color = (80, 140, 255, 180)

    box = Image.new("RGBA", (W-80, BOX_H), (0,0,0,0))
    bd  = ImageDraw.Draw(box)

    bd.rounded_rectangle((0,0,W-80,BOX_H), radius=45, fill=fill_color, outline=outline_color, width=3)
    card.alpha_composite(box, (40, BOX_Y))

    # DMV text
    ot(60, BOX_Y+15, "DMV INFO:", section, blue)
    draw.line((60, BOX_Y+47, 300, BOX_Y+47), fill=blue, width=3)

    y2 = BOX_Y + 65
    draw.text((60, y2), "License Class:", font=boldf, fill=grey)
    draw.text((245, y2), "Provisional" if license_type=="provisional" else "Standard", font=normal, fill=grey)

    draw.text((430, y2), f"License #: {lic_num_str}", font=normal, fill=grey)

    y2 += 38
    draw.text((60, y2), "Issued:", font=boldf, fill=grey)
    draw.text((150, y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    draw.text((330, y2), "Expires:", font=boldf, fill=grey)
    draw.text((430, y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    # ====================================================
    # STAR SEAL
    # ====================================================
    seal = Image.new("RGBA", (95,95), (0,0,0,0))
    sd = ImageDraw.Draw(seal)

    cx, cy = 48, 48
    R1, R2 = 44, 19
    pts = []

    for i in range(16):
        ang = math.radians(i * 22.5)
        r = R1 if i % 2 == 0 else R2
        pts.append((cx + r*math.cos(ang), cy + r*math.sin(ang)))

    if license_type == "provisional":
        seal_color = (255,150,40)
        outline_c  = (255,230,180)
    else:
        seal_color = (40,90,180)
        outline_c  = (255,255,255)

    sd.polygon(pts, fill=seal_color, outline=outline_c, width=3)
    seal = seal.filter(ImageFilter.GaussianBlur(1.0))

    card.alpha_composite(seal, (W-150, BOX_Y+10))

    # ====================================================
    # EXPORT BUFFER
    # ====================================================
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
