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
    # OUTER SHADOW
    # =============================
    shadow = Image.new("RGBA", (W + 50, H + 50), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((25, 25, W + 25, H + 25), radius=70, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))

    img = shadow.copy()

    # Main card with curve
    card = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=70, fill=255)
    img.paste(card, (25, 25), mask)

    card = img.copy().crop((25, 25, W + 25, H + 25))
    draw = ImageDraw.Draw(card)

    # Colors
    header_blue = (35, 70, 140)
    grey_dark = (40, 40, 40)
    grey_mid = (75, 75, 75)
    blue_accent = (50, 110, 200)
    mesh_color = (200, 200, 215, 55)
    border_grey = (200, 200, 200)
    dmv_gold = (225, 190, 90)

    # Fonts
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(16)
    section_font = load_font(24, bold=True)

    # =============================
    # HEADER BAR (same, title updated)
    # =============================
    header = Image.new("RGBA", (W, 95), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))

    card.paste(header, (0, 0), header)

    header_text = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(header_text, font=title_font)
    draw.text(((W - tw) / 2, 25), header_text, fill="white", font=title_font)

    # =============================
    # BACKGROUND MESH (keep)
    # =============================
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)

    spacing = 34
    for y in range(120, H, spacing):
        for x in range(0, W, spacing):
            md.line((x, y, x + spacing // 2, y + spacing // 2), fill=mesh_color, width=2)
            md.line((x + spacing // 2, y, x, y + spacing // 2), fill=mesh_color, width=2)

    mesh = mesh.filter(ImageFilter.GaussianBlur(0.7))
    card = Image.alpha_composite(card, mesh)
    draw = ImageDraw.Draw(card)

    # =============================
    # WATERMARK (center)
    # =============================
    wm_text = "LAKEVIEW"
    wm_font = load_font(110, bold=True)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wmd = ImageDraw.Draw(wm_layer)

    tw = wmd.textlength(wm_text, font=wm_font)
    timg = Image.new("RGBA", (int(tw) + 40, 200), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(timg)
    tdraw.text((20, 0), wm_text, font=wm_font, fill=(150, 150, 150, 35))

    timg = timg.rotate(28, expand=True)
    timg = timg.filter(ImageFilter.GaussianBlur(1.3))
    wm_layer.paste(timg, (W // 2 - timg.width // 2, H // 3), timg)

    card = Image.alpha_composite(card, wm_layer)
    draw = ImageDraw.Draw(card)

    # =============================
    # AVATAR (left)
    # =============================
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))

        mask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        av.putalpha(mask)

        shadow_av = av.filter(ImageFilter.GaussianBlur(4))
        card.paste(shadow_av, (58, 153), shadow_av)
        card.paste(av, (50, 145), av)

    except:
        pass

    # =============================
    # IDENTITY / PHYSICAL HEADERS
    # =============================
    # Identity left
    ix = 300
    iy = 150

    draw.text((ix, iy), "IDENTITY", font=section_font, fill=blue_accent)
    draw.line((ix, iy + 32, ix + 240, iy + 32), fill=blue_accent, width=3)

    # Physical right (shifted more right)
    px = 550
    py = 150

    draw.text((px, py), "PHYSICAL", font=section_font, fill=blue_accent)
    draw.line((px, py + 32, px + 230, py + 32), fill=blue_accent, width=3)

    # =============================
    # IDENTITY FIELDS
    # =============================
    iy += 55
    draw.text((ix, iy), "Name:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), roleplay_name or username, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Age:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), age, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Address:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), address, font=value_font, fill=grey_mid)

    # =============================
    # PHYSICAL FIELDS
    # =============================
    py += 55
    draw.text((px, py), "Eye Color:", font=label_font, fill=grey_dark)
    draw.text((px + 135, py), eye_color, font=value_font, fill=grey_mid)
    py += 32

    draw.text((px, py), "Height:", font=label_font, fill=grey_dark)
    draw.text((px + 135, py), height, font=value_font, fill=grey_mid)

    # =============================
    # DMV INFO BOX (full width, curved)
    # =============================
    BOX_Y = 330
    BOX_H = 160

    box = Image.new("RGBA", (W - 80, BOX_H), (255, 255, 255, 255))
    bdraw = ImageDraw.Draw(box)
    bdraw.rounded_rectangle((0, 0, W - 80, BOX_H), radius=35, outline=border_grey, width=3)

    # Paste box
    card.paste(box, (40, BOX_Y), box)

    # DMV Info Title
    draw.text((60, BOX_Y + 20), "DMV INFO", font=section_font, fill=blue_accent)
    draw.line((60, BOX_Y + 52, 300, BOX_Y + 52), fill=blue_accent, width=3)

    # DMV Info text
    y2 = BOX_Y + 70
    draw.text((60, y2), "License Class: Standard", font=label_font, fill=grey_dark); y2 += 32
    draw.text((60, y2), f"Issued: {issued.strftime('%Y-%m-%d')}", font=label_font, fill=grey_dark); y2 += 32
    draw.text((60, y2), f"Expires: {expires.strftime('%Y-%m-%d')}", font=label_font, fill=grey_dark)

    # =============================
    # DMV CERT Seal (inside box)
    # =============================
    seal = Image.new("RGBA", (130, 130), (0, 0, 0, 0))
    s = ImageDraw.Draw(seal)

    s.ellipse((5, 5, 125, 125), outline=(150, 200, 255, 90), width=4)
    s.text((38, 45), "DMV\nCERTIFIED", fill=dmv_gold, font=small_font, align="center")

    seal = seal.filter(ImageFilter.GaussianBlur(0.6))

    card.paste(seal, (W - 200, BOX_Y + 20), seal)

    # =============================
    # SAVE
    # =============================
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
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
                await channel.send(f"<@{discord_id}> Your license has been issued!", embed=embed, file=file)

            if discord_id:
                try:
                    user = await bot.fetch_user(int(discord_id))
                    if user:
                        dm_embed = discord.Embed(
                            title="Your Lakeview City Driver’s License",
                            color=0x757575
                        )
                        dm_embed.set_image(url=f"attachment://{filename}")
                        await user.send(embed=dm_embed, file=make_file(img_data, filename))
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
