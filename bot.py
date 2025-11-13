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
# FONT LOADING
# ======================

def load_font(size: int, bold: bool = False):
    """Load a clean sans-serif font with fallbacks."""
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

    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except:
            pass

    return ImageFont.load_default()


# =================================
# LICENSE IMAGE GENERATOR
# =================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520
    radius = 60

    # IMPORTANT: FULLY OPAQUE WHITE BACKGROUND
    card_bg = (250, 250, 252, 255)

    # Draw onto an opaque card, not transparent
    card = Image.new("RGBA", (W, H), card_bg)

    # Rounded mask
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=radius, fill=255)

    # Apply the rounded shape
    card.putalpha(mask)

    draw = ImageDraw.Draw(card)

    # COLORS
    header_blue = (35, 70, 140, 255)
    grey_dark = (40, 40, 40, 255)
    grey_mid = (75, 75, 75, 255)
    blue_accent = (50, 110, 200, 255)
    mesh_color = (225, 225, 235, 70)
    dmv_gold = (225, 190, 90, 255)

    # FONTS
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(16)
    section_font = load_font(24, bold=True)

    # HEADER
    header_rect = Image.new("RGBA", (W, 95), header_blue)
    header_mask = Image.new("L", (W, 95), 0)
    ImageDraw.Draw(header_mask).rounded_rectangle((0, 0, W, 95), radius=radius, fill=255)

    card.paste(header_rect, (0, 0), header_mask)

    header_text = "Lakeview City • Driver’s License"
    tw = draw.textlength(header_text, font=title_font)
    draw.text(((W - tw) / 2, 25), header_text, fill="white", font=title_font)

    # MESH PATTERN — must be clipped INSIDE card
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mesh)

    for y in range(110, H, 28):
        for x in range(0, W, 28):
            mdraw.line((x, y, x+14, y+14), fill=mesh_color, width=2)
            mdraw.line((x+14, y, x, y+14), fill=mesh_color, width=2)

    mesh.putalpha(mask)
    card = Image.alpha_composite(card, mesh)
    draw = ImageDraw.Draw(card)

    # WATERMARK
    wm_text = "LAKEVIEW"
    wm_font = load_font(90, bold=True)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wm_layer)

    tw = wdraw.textlength(wm_text, font=wm_font)
    tmp = Image.new("RGBA", (int(tw)+20, 120), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tmp)
    tdraw.text((10, 0), wm_text, font=wm_font, fill=(160, 160, 160, 45))
    tmp = tmp.rotate(33, expand=True).filter(ImageFilter.GaussianBlur(1))

    wm_layer.paste(tmp, (W//2 - tmp.width//2, H//2 - tmp.height//2), tmp)
    wm_layer.putalpha(mask)
    card = Image.alpha_composite(card, wm_layer)
    draw = ImageDraw.Draw(card)

    # AVATAR
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((200, 200))
        amask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(amask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        avatar.putalpha(amask)
        card.paste(avatar, (45, 135), avatar)
    except:
        pass

    # SECTION HELPERS
    def section_header(title, x, y):
        draw.text((x, y), title, fill=blue_accent, font=section_font)
        draw.line((x, y+30, x+300, y+30), fill=blue_accent, width=3)

    def field(label, value, x, y):
        draw.text((x, y), label, fill=grey_dark, font=label_font)
        lw = draw.textlength(label, font=label_font)
        draw.text((x + lw + 8, y), value or "N/A", fill=grey_mid, font=value_font)

    # IDENTITY
    ix = 280
    y = 140
    section_header("IDENTITY", ix, y)
    y += 55
    field("Name:", roleplay_name or username, ix, y); y += 40
    field("Age:", age, ix, y); y += 40
    field("Address:", address, ix, y); y += 50

    # PHYSICAL
    section_header("PHYSICAL", ix, y)
    y += 55
    field("Eye Color:", eye_color, ix, y); y += 40
    field("Height:", height, ix, y)

    # DMV INFO BELOW AVATAR
    dmv_y = 360
    section_header("DMV INFO", 45, dmv_y)
    dmv_y += 55

    draw.text((45, dmv_y), "License Class: Standard", fill=grey_dark, font=label_font)
    draw.text((45, dmv_y + 32), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)
    draw.text((45, dmv_y + 64), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)

    # Notes (two lines)
    notes_y = dmv_y + 110
    draw.text((45, notes_y), "This license is property of the Lakeview City DMV.", fill=grey_mid, font=small_font)
    draw.text((45, notes_y + 22), "Tampering, duplication, or misuse is prohibited by law.", fill=grey_mid, font=small_font)

    # DMV SEAL
    seal = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    sdraw.ellipse((0,0,180,180), outline=(255,220,120,90), width=6)
    sdraw.ellipse((10,10,170,170), outline=(160,200,255,90), width=4)
    sdraw.ellipse((25,25,155,155), outline=(255,150,200,90), width=3)
    sdraw.text((52,70), "Lakeview\nCity DMV\nCertified", fill=dmv_gold, font=small_font, align="center")
    seal = seal.filter(ImageFilter.GaussianBlur(0.6))
    card.paste(seal, (W-220, 150), seal)

    # EXPORT — MUST REMAIN OPAQUE
    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out.read()


# ======================
# FLASK API
# ======================

app = Flask(__name__)

def make_file(img_bytes, filename):
    return discord.File(io.BytesIO(img_bytes), filename=filename)


@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json or {}

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")

        if not username or not avatar_url:
            return jsonify({"status": "error", "message": "Missing"}), 400

        avatar_bytes = requests.get(avatar_url, timeout=10).content

        img_bytes = create_license_image(
            username=username,
            avatar_bytes=avatar_bytes,
            roleplay_name=data.get("roleplay_name"),
            age=data.get("age"),
            address=data.get("address"),
            eye_color=data.get("eye_color"),
            height=data.get("height"),
            issued=datetime.utcnow(),
            expires=datetime.utcnow(),
            lic_num="AUTO"
        )

        filename = f"{username}_license.png"

        async def send_license():
            await bot.wait_until_ready()

            channel = bot.get_channel(1436890841703645285)

            file = make_file(img_bytes, filename)

            if channel:
                embed = discord.Embed(
                    title="Lakeview City Roleplay Driver’s License",
                    color=0x757575
                )
                embed.set_image(url=f"attachment://{filename}")

                await channel.send(
                    content=f"<@{data.get('discord_id')}> Your license has been issued!",
                    embed=embed,
                    file=file
                )

            if data.get("discord_id"):
                try:
                    user = await bot.fetch_user(int(data["discord_id"]))
                    if user:
                        dm_embed = discord.Embed(
                            title="Your Lakeview City Driver’s License",
                            color=0x757575
                        )
                        dm_embed.set_image(url=f"attachment://{filename}")
                        await user.send(embed=dm_embed, file=make_file(img_bytes, filename))
                except:
                    pass

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("[ERROR]", e)
        return jsonify({"status": "error"}), 500


# ======================
# COMMANDS
# ======================

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency*1000)}ms`")


# ======================
# READY
# ======================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


# ======================
# RUN
# ======================

def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Starting Flask")
    app.run(host="0.0.0.0", port=8080)
