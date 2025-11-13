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
#  FONT LOADER
# ======================

def load_font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf"
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            continue
    return ImageFont.load_default()



# =================================
#  LICENSE IMAGE GENERATOR
# =================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520

    # FULLY TRANSPARENT BASE (no black outside card)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Rounded card mask
    radius = 60
    card_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(card_mask).rounded_rectangle((0, 0, W, H), radius=radius, fill=255)

    # Card base (opaque white-ish background)
    card = Image.new("RGBA", (W, H), (250, 250, 252, 255))
    card = Image.composite(card, canvas, card_mask)

    draw = ImageDraw.Draw(card)

    # COLORS
    header_blue = (35, 70, 140, 255)
    grey_dark = (40, 40, 40, 255)
    grey_mid = (75, 75, 75, 255)
    blue_accent = (50, 110, 200, 255)
    mesh_color = (225, 225, 235, 70)
    dmv_gold = (225, 190, 90, 255)
    holo1 = (255, 220, 120, 90)
    holo2 = (160, 200, 255, 90)
    holo3 = (255, 150, 200, 90)

    # FONTS
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22, bold=False)
    small_font = load_font(16, bold=False)
    section_font = load_font(24, bold=True)

    # ======================
    # HEADER BAR
    # ======================
    draw.rounded_rectangle((0, 0, W, 95), radius=radius, fill=header_blue)
    title = "Lakeview City • Driver’s License"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 25), title, fill="white", font=title_font)

    # ======================
    # X MESH — CONTAINED WITHIN CARD
    # ======================
    mesh_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mesh_layer)

    for y in range(110, H, 28):
        for x in range(0, W, 28):
            mdraw.line((x, y, x + 14, y + 14), fill=mesh_color, width=2)
            mdraw.line((x + 14, y, x, y + 14), fill=mesh_color, width=2)

    mesh_layer.putalpha(card_mask)
    card = Image.alpha_composite(card, mesh_layer)
    draw = ImageDraw.Draw(card)

    # ======================
    # WATERMARK
    # ======================
    wm_text = "LAKEVIEW"
    wm_font = load_font(90, bold=True)
    wml = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    t = Image.new("RGBA", (500, 150), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((0, 0), wm_text, font=wm_font, fill=(150, 150, 150, 40))
    t = t.rotate(33, expand=True).filter(ImageFilter.GaussianBlur(1))

    wml.paste(t, (int(W/2 - t.width/2), int(H/2 - t.height/2)), t)
    wml.putalpha(card_mask)
    card = Image.alpha_composite(card, wml)
    draw = ImageDraw.Draw(card)

    # ======================
    # AVATAR
    # ======================
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((200, 200))
        amask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(amask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        avatar.putalpha(amask)
        card.paste(avatar, (45, 135), avatar)
    except:
        pass

    # ======================
    # SECTION HELPERS
    # ======================
    def section_header(title, x, y):
        draw.text((x, y), title, fill=blue_accent, font=section_font)
        draw.line((x, y + 30, x + 300, y + 30), fill=blue_accent, width=3)

    def field(label, value, x, y):
        draw.text((x, y), label, fill=grey_dark, font=label_font)
        lw = draw.textlength(label, font=label_font)
        draw.text((x + lw + 10, y), value or "N/A", fill=grey_mid, font=value_font)

    # ======================
    # IDENTITY
    # ======================
    x = 280
    y = 140

    section_header("IDENTITY", x, y)
    y += 50
    field("Name:", roleplay_name or username, x, y); y += 36
    field("Age:", age, x, y); y += 36
    field("Address:", address, x, y); y += 45

    # ======================
    # PHYSICAL
    # ======================
    section_header("PHYSICAL", x, y)
    y += 50
    field("Eye Color:", eye_color, x, y); y += 36
    field("Height:", height, x, y)

    # ======================
    # FIXED DMV INFO — CLEAN, SPREAD OUT, NO OVERLAP
    # ======================
    dmv_x = 45
    dmv_y = 355

    section_header("DMV INFO", dmv_x, dmv_y)
    dmv_y += 50

    draw.text((dmv_x, dmv_y), "License Class: Standard", fill=grey_dark, font=label_font)
    draw.text((dmv_x + 320, dmv_y), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)
    draw.text((dmv_x + 600, dmv_y), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)

    # NOTES — placed lower cleanly
    notes_y = dmv_y + 55
    draw.text((dmv_x, notes_y), "This license is property of the Lakeview City DMV.", fill=grey_mid, font=small_font)
    draw.text((dmv_x, notes_y + 20), "Tampering, duplication, or misuse is prohibited by law.", fill=grey_mid, font=small_font)

    # ======================
    # DMV HOLOGRAPHIC SEAL
    # ======================
    seal = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)

    sdraw.ellipse((0, 0, 180, 180), outline=holo1, width=6)
    sdraw.ellipse((10, 10, 170, 170), outline=holo2, width=4)
    sdraw.ellipse((25, 25, 155, 155), outline=holo3, width=3)

    sdraw.text((52, 70), "Lakeview\nCity DMV\nCertified",
               fill=dmv_gold, font=small_font, align="center")

    seal = seal.filter(ImageFilter.GaussianBlur(0.6))
    card.paste(seal, (W - 220, 150), seal)

    # ======================
    # RETURN IMAGE BYTES
    # ======================
    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()



# ======================
#  FLASK API
# ======================

app = Flask(__name__)

def make_file(img_bytes, name):
    return discord.File(io.BytesIO(img_bytes), filename=name)



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

        avatar_bytes = requests.get(avatar_url, timeout=10).content

        img_data = create_license_image(
            username, avatar_bytes, roleplay_name, age, address,
            eye_color, height, datetime.utcnow(), datetime.utcnow(),
            "AUTO"
        )

        filename = f"{username}_license.png"

        async def send():
            await bot.wait_until_ready()

            file = make_file(img_data, filename)

            channel = bot.get_channel(1436890841703645285)
            if channel:
                embed = discord.Embed(
                    title="Lakeview City Roleplay Driver’s License",
                    color=0x757575,
                )
                embed.set_image(url=f"attachment://{filename}")
                await channel.send(content=f"<@{discord_id}> Your license has been issued!", embed=embed, file=file)

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

        bot.loop.create_task(send())
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# ======================
#  COMMANDS
# ======================

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency * 1000)}ms`")



# ======================
#  BOOTSTRAP
# ======================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Starting Flask server...")
    app.run(host="0.0.0.0", port=8080)
