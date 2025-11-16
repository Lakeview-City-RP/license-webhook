from __future__ import annotations

# --- stdlib ---
import os, io, json
from datetime import datetime
from threading import Thread

# --- third-party ---
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py ---
import discord
from discord.ext import commands


# =======================
#  TOKEN / DISCORD SETUP
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
#  FONT LOADING HANDLER
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

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue

    return ImageFont.load_default()


# =================================
#  LICENSE CARD IMAGE GENERATOR
# =================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520

    # =============================
    # CARD SHADOW BASE
    # =============================
    shadow = Image.new("RGBA", (W + 40, H + 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((20, 20, W + 20, H + 20), radius=60, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))

    img = shadow.copy()
    card = Image.new("RGBA", (W, H), (250, 250, 252, 255))
    draw = ImageDraw.Draw(card)

    # COLORS
    header_blue = (35, 70, 140)
    grey_dark = (40, 40, 40)
    grey_mid = (75, 75, 75)
    blue_accent = (50, 110, 200)
    mesh_color = (200, 200, 215, 65)
    dmv_gold = (225, 190, 90)

    # FONTS
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(16)
    section_font = load_font(24, bold=True)

    # =============================
    # HEADER BAR
    # =============================
    header = Image.new("RGBA", (W, 95), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))

    card.paste(header, (0, 0))

    header_text = "Lakeview City • Driver’s License"
    tw = draw.textlength(header_text, font=title_font)
    draw.text(((W - tw) / 2, 25), header_text, fill="white", font=title_font)

    # =============================
    # MESH BACKGROUND
    # =============================
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)

    spacing = 34
    for y in range(110, H, spacing):
        for x in range(0, W, spacing):
            md.line((x, y, x + spacing // 2, y + spacing // 2), fill=mesh_color, width=2)
            md.line((x + spacing // 2, y, x, y + spacing // 2), fill=mesh_color, width=2)

    mesh = mesh.filter(ImageFilter.GaussianBlur(0.7))
    card = Image.alpha_composite(card, mesh)
    draw = ImageDraw.Draw(card)

    # =============================
    # WATERMARK
    # =============================
    wm_text = "LAKEVIEW"
    wm_font = load_font(90, bold=True)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wmd = ImageDraw.Draw(wm_layer)

    tw = wmd.textlength(wm_text, font=wm_font)
    tmp = Image.new("RGBA", (int(tw) + 20, 120), (0, 0, 0, 0))
    tmd = ImageDraw.Draw(tmp)
    tmd.text((10, 0), wm_text, font=wm_font, fill=(160, 160, 160, 40))
    tmp = tmp.rotate(33, expand=True)
    tmp = tmp.filter(ImageFilter.GaussianBlur(1))

    wm_layer.paste(tmp, (W // 2 - tmp.width // 2, H // 3), tmp)
    card = Image.alpha_composite(card, wm_layer)
    draw = ImageDraw.Draw(card)

    # =============================
    # AVATAR
    # =============================
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))

        mask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        av.putalpha(mask)

        shadow_av = av.filter(ImageFilter.GaussianBlur(4))
        card.paste(shadow_av, (53, 143), shadow_av)
        card.paste(av, (45, 135), av)

    except:
        pass

    # =============================
    # IDENTITY SECTION
    # =============================
    ix = 280
    iy = 140

    draw.text((ix, iy), "IDENTITY", fill=blue_accent, font=section_font)
    draw.line((ix, iy + 32, ix + 260, iy + 32), fill=blue_accent, width=3)

    iy += 50
    draw.text((ix, iy), "Name:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), roleplay_name or username, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Age:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), age, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Address:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), address, font=value_font, fill=grey_mid)

    # =============================
    # PHYSICAL SECTION
    # =============================
    px = 520
    py = 140

    draw.text((px, py), "PHYSICAL", fill=blue_accent, font=section_font)
    draw.line((px, py + 32, px + 260, py + 32), fill=blue_accent, width=3)

    py += 50
    draw.text((px, py), "Eye Color:", font=label_font, fill=grey_dark)
    draw.text((px + 130, py), eye_color, font=value_font, fill=grey_mid)
    py += 32

    draw.text((px, py), "Height:", font=label_font, fill=grey_dark)
    draw.text((px + 130, py), height, font=value_font, fill=grey_mid)

    # =============================
    # DMV INFO
    # =============================
    dmv_y = 350

    draw.text((45, dmv_y), "DMV INFO", font=section_font, fill=blue_accent)
    draw.line((45, dmv_y + 32, 350, dmv_y + 32), fill=blue_accent, width=3)

    dmv_y += 55
    draw.text((45, dmv_y), "License Class: Standard", fill=grey_dark, font=label_font); dmv_y += 32
    draw.text((45, dmv_y), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font); dmv_y += 32
    draw.text((45, dmv_y), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font); dmv_y += 40

    # =============================
    # DMV SEAL (small, bottom-right)
    # =============================
    seal = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    s = ImageDraw.Draw(seal)

    s.ellipse((5, 5, 115, 115), outline=(150, 200, 255, 85), width=4)
    s.text((28, 45), "DMV\nCERTIFIED", font=small_font, fill=dmv_gold, align="center")

    seal = seal.filter(ImageFilter.GaussianBlur(0.5))
    card.paste(seal, (W - 150, H - 170), seal)

    # MERGE
    img.paste(card, (20, 20), card)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ======================
#  FLASK WEB API
# ======================

app = Flask(__name__)

def make_file(img_bytes: bytes, filename: str) -> discord.File:
    return discord.File(io.BytesIO(img_bytes), filename=filename)


@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json or {}

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")
        roleplay_name = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye_color = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")

        if not username or not avatar_url:
            return jsonify({"status": "error", "message": "Missing username or avatar"}), 400

        avatar_bytes = requests.get(avatar_url, timeout=10).content

        img_data = create_license_image(
            username, avatar_bytes, roleplay_name, age, address,
            eye_color, height, datetime.utcnow(), datetime.utcnow(),
            "AUTO"
        )
        filename = f"{username}_license.png"

        async def send_license():
            await bot.wait_until_ready()

            file = make_file(img_data, filename)

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

            if discord_id:
                try:
                    user = await bot.fetch_user(int(discord_id))
                    if user:
                        dm_embed = discord.Embed(
                            title="Your Lakeview City Driver’s License",
                            color=0x757575
                        )
                        dm_embed.set_image(url=f"attachment://{filename}")
                        await user.send(
                            embed=dm_embed,
                            file=make_file(img_data, filename)
                        )
                except Exception as e:
                    print("[DM Error]", e)

        bot.loop.create_task(send_license())

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print("[Webhook Error]", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================
#  BASIC COMMANDS
# ======================

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency * 1000)}ms`")


# ======================
#  BOT READY
# ======================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


# ======================
#  RUN EVERYTHING
# ======================

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Starting Flask server...")
    app.run(host="0.0.0.0", port=8080)
