from __future__ import annotations

# --- stdlib ---
import os, io
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

    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass

    return ImageFont.load_default()


# =================================
#  LICENSE CARD IMAGE GENERATOR
# =================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):
    print("→ create_license_image CALLED")

    print("→ Drawing header...")
    print("→ Drawing mesh...")
    print("→ Drawing watermark...")
    print("→ Drawing avatar...")
    print("→ Drawing Identity/Physical...")
    print("→ Drawing DMV Box...")
    print("→ Drawing Shield...")
    print("→ Exporting PNG...")

    W, H = 820, 520

    # -----------------------------
    # FULL CARD MASK (CURVED)
    # -----------------------------
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=70, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    base.putalpha(mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    # Colors
    header_blue = (35, 70, 140)
    grey_dark = (40, 40, 40)
    grey_mid = (75, 75, 75)
    blue_accent = (50, 110, 200)
    mesh_color = (200, 200, 215, 50)
    dmv_gold = (225, 190, 90)
    box_bg = (200, 220, 255, 100)
    box_border = (80, 140, 255, 170)

    # Fonts
    title_font = load_font(42, bold=True)
    section_font = load_font(24, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(16)
    wm_font = load_font(110, bold=True)

    # -----------------------------
    # HEADER BAR
    # -----------------------------
    header = Image.new("RGBA", (W, 95))
    hd = ImageDraw.Draw(header)

    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))

    header.putalpha(mask)
    card.paste(header, (0, 0), header)

    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 25), title, fill="white", font=title_font)

    # -----------------------------
    # X-PATTERN BACKGROUND
    # -----------------------------
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)
    spacing = 34

    for y in range(120, H, spacing):
        for x in range(0, W, spacing):
            md.line((x, y, x + spacing // 2, y + spacing // 2),
                    fill=mesh_color, width=2)
            md.line((x + spacing // 2, y, x, y + spacing // 2),
                    fill=mesh_color, width=2)

    mesh.putalpha(mask)
    mesh = mesh.filter(ImageFilter.GaussianBlur(0.7))
    card = Image.alpha_composite(card, mesh)
    draw = ImageDraw.Draw(card)

    # -----------------------------
    # WATERMARK
    # -----------------------------
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wmd = ImageDraw.Draw(wm_layer)

    wm_text = "LAKEVIEW"
    tw = wmd.textlength(wm_text, font=wm_font)
    timg = Image.new("RGBA", (int(tw) + 40, 200))
    td = ImageDraw.Draw(timg)
    td.text((20, 0), wm_text, font=wm_font, fill=(150, 150, 150, 35))

    timg = timg.rotate(28, expand=True)
    timg = timg.filter(ImageFilter.GaussianBlur(1.2))
    wm_layer.paste(timg, (W // 2 - timg.width // 2, H // 3), timg)

    wm_layer.putalpha(mask)
    card = Image.alpha_composite(card, wm_layer)
    draw = ImageDraw.Draw(card)

    # -----------------------------
    # AVATAR
    # -----------------------------
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))
        mask_av = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(mask_av).rounded_rectangle(
            (0, 0, 200, 200), radius=35, fill=255)
        av.putalpha(mask_av)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.paste(shadow, (58, 153), shadow)
        card.paste(av, (50, 145), av)
    except:
        pass

    # -----------------------------
    # IDENTITY + PHYSICAL
    # -----------------------------
    ix = 300
    iy = 150
    draw.text((ix, iy), "IDENTITY", font=section_font, fill=blue_accent)
    draw.line((ix, iy + 34, ix + 240, iy + 34),
              fill=blue_accent, width=3)

    px = 550
    py = 150
    draw.text((px, py), "PHYSICAL", font=section_font, fill=blue_accent)
    draw.line((px, py + 34, px + 240, py + 34),
              fill=blue_accent, width=3)

    # IDENTITY FIELDS
    iy += 55
    draw.text((ix, iy), "Name:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), roleplay_name or username,
              font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Age:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), age,
              font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Address:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), address,
              font=value_font, fill=grey_mid)

    # PHYSICAL FIELDS
    py += 55
    draw.text((px, py), "Eye Color:", font=label_font, fill=grey_dark)
    draw.text((px + 140, py), eye_color,
              font=value_font, fill=grey_mid)
    py += 32

    draw.text((px, py), "Height:", font=label_font, fill=grey_dark)
    draw.text((px + 140, py), height,
              font=value_font, fill=grey_mid)

    # -----------------------------
    # DMV INFO BOX
    # -----------------------------
    BOX_Y = 345
    BOX_H = 150

    box = Image.new("RGBA", (W - 80, BOX_H))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle(
        (0, 0, W - 80, BOX_H),
        radius=35,
        fill=box_bg,
        outline=box_border,
        width=3
    )

    card.paste(box, (40, BOX_Y), box)
    draw = ImageDraw.Draw(card)

    draw.text((60, BOX_Y + 15), "DMV INFO",
              font=section_font, fill=blue_accent)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47),
              fill=blue_accent, width=3)

    y2 = BOX_Y + 60
    draw.text((60, y2), "License Class: Standard",
              fill=grey_dark, font=label_font)
    y2 += 30
    draw.text((60, y2), f"Issued: {issued.strftime('%Y-%m-%d')}",
              fill=grey_dark, font=label_font)
    y2 += 30
    draw.text((60, y2), f"Expires: {expires.strftime('%Y-%m-%d')}",
              fill=grey_dark, font=label_font)

    # -----------------------------
    # DMV SHIELD
    # -----------------------------
    shield = Image.new("RGBA", (110, 110), (255, 255, 255, 0))
    sd = ImageDraw.Draw(shield)

    sd.polygon(
        [(55, 5), (100, 35), (90, 90), (20, 90), (10, 35)],
        fill=(255, 255, 255, 230),
        outline=(80, 140, 255),
        width=4
    )
    sd.text((29, 40), "DMV\nCERT", fill=dmv_gold,
            font=small_font, align="center")

    shield = shield.filter(ImageFilter.GaussianBlur(0.3))
    card.paste(shield, (W - 120, BOX_Y + 25), shield)

    # -----------------------------
    # EXPORT PNG
    # -----------------------------
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ======================
#  DISCORD SENDER
# ======================

async def send_license_to_discord(img_data, filename, discord_id):
    await bot.wait_until_ready()
    file = discord.File(io.BytesIO(img_data), filename=filename)

    channel = bot.get_channel(1436890841703645285)
    if channel:
        embed = discord.Embed(
            title="Lakeview City Roleplay Driver’s License", color=0x757575)
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
                dm = discord.Embed(
                    title="Your Lakeview City Driver’s License", color=0x757575)
                dm.set_image(url=f"attachment://{filename}")
                await user.send(embed=dm, file=discord.File(
                    io.BytesIO(img_data), filename=filename))
        except:
            pass


# ======================
#  FLASK API
# ======================

app = Flask(__name__)


@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        print("\n=== Incoming /license request ===")
        print("JSON:", request.json)

        data = request.json or {}

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")
        roleplay_name = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye_color = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")
        license_id = data.get("license_id") or username

        if not username or not avatar_url:
            print("❌ Missing username or avatar URL")
            return jsonify({"status": "error", "message": "Missing username/avatar"}), 400

        print("→ Downloading avatar...")
        avatar_bytes = requests.get(avatar_url).content

        print("→ Creating license image...")
        img = create_license_image(
            username, avatar_bytes, roleplay_name, age, address,
            eye_color, height, datetime.utcnow(), datetime.utcnow(), license_id
        )

        print("→ Sending to Discord...")
        bot.loop.create_task(send_license_to_discord(img, f"{username}_license.png", discord_id))

        print("→ DONE")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print("\n" + "!"*60)
        print("🔥 ERROR IN /license ENDPOINT")
        print("TYPE:", type(e))
        print("MESSAGE:", str(e))
        print("TRACEBACK:")
        print(traceback.format_exc())
        print("!"*60 + "\n")
        return jsonify({"status": "error"}), 500


# ======================
#  BOT COMMANDS
# ======================

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency*1000)}ms`")


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
