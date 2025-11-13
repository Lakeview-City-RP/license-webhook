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

# Optional local fallback for development
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
    """Loads a clean sans-serif font, falling back safely."""
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
        except Exception:
            continue

    return ImageFont.load_default()


# =================================
#  LICENSE CARD IMAGE GENERATOR
# =================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520  # compact ERLC-style
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # COLORS
    header_blue = (35, 70, 140, 255)
    card_bg = (250, 250, 252, 255)
    grey_dark = (40, 40, 40, 255)
    grey_mid = (75, 75, 75, 255)
    blue_accent = (50, 110, 200, 255)
    grid_color = (200, 200, 215, 70)
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

    # =====================
    # Rounded Card Base
    # =====================
    radius = 60
    base = Image.new("RGBA", (W, H), card_bg)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=radius, fill=255)
    img.paste(base, (0, 0), mask)

    # =====================
    # Header Bar
    # =====================
    draw.rounded_rectangle((0, 0, W, 95), radius=60, fill=header_blue)
    header_text = "Lakeview City • Driver’s License"
    tw = draw.textlength(header_text, font=title_font)
    draw.text(((W - tw) / 2, 25), header_text, fill="white", font=title_font)

    # =====================
    # MESH BACKGROUND PATTERN
    # =====================
    # Diagonal mesh pattern — soft, realistic
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mesh)

    for y in range(110, H, 28):
        for x in range(0, W, 28):
            mdraw.line((x, y, x + 14, y + 14), fill=mesh_color, width=2)
            mdraw.line((x + 14, y, x, y + 14), fill=mesh_color, width=2)

    img = Image.alpha_composite(img, mesh)
    draw = ImageDraw.Draw(img)

    # =====================
    # Small, Subtle Watermark
    # =====================
    wm_text = "LAKEVIEW"
    wm_font = load_font(90, bold=True)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wm_layer)

    tw = wdraw.textlength(wm_text, font=wm_font)
    tmp = Image.new("RGBA", (int(tw) + 20, 120), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tmp)
    tdraw.text((10, 0), wm_text, font=wm_font, fill=(160, 160, 160, 50))
    tmp = tmp.rotate(33, expand=True)
    tmp = tmp.filter(ImageFilter.GaussianBlur(1))

    wm_layer.paste(tmp, (W//2 - tmp.width//2, H//2 - tmp.height//2), tmp)
    img = Image.alpha_composite(img, wm_layer)
    draw = ImageDraw.Draw(img)

    # =====================
    # AVATAR
    # =====================
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((200, 200))
        amask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(amask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        avatar.putalpha(amask)
        img.paste(avatar, (45, 135), avatar)
    except:
        pass

    # =====================
    # TEXT SECTIONS
    # =====================

    # Section helper
    def section_header(title, x, y):
        draw.text((x, y), title, fill=blue_accent, font=section_font)
        line_y = y + 30
        draw.line((x, line_y, x + 300, line_y), fill=blue_accent, width=3)

    # Field helper
    def field(label, value, x, y):
        draw.text((x, y), label, fill=grey_dark, font=label_font)
        lw = draw.textlength(label, font=label_font)
        draw.text((x + lw + 8, y), value or "N/A", font=value_font, fill=grey_mid)

    # -----------------------
    # IDENTITY
    # -----------------------
    ix = 280
    y = 140

    section_header("IDENTITY", ix, y)
    y += 50

    field("Name:", roleplay_name or username, ix, y); y += 36
    field("Age:", age, ix, y); y += 36
    field("Address:", address, ix, y); y += 40

    # -----------------------
    # PHYSICAL
    # -----------------------
    section_header("PHYSICAL", ix, y)
    y += 50

    field("Eye Color:", eye_color, ix, y); y += 36
    field("Height:", height, ix, y); y += 50

    # -----------------------
    # DMV INFO (Left-aligned under avatar)
    # -----------------------
    dmv_y = 350
    section_header("DMV INFO", 50, dmv_y)
    dmv_y += 50

    draw.text((50, dmv_y), f"License Class: Standard", fill=grey_dark, font=label_font)
    draw.text((50, dmv_y + 32), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)
    draw.text((50, dmv_y + 64), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)

    # =====================
    # NOTES
    # =====================
    notes_y = 440
    draw.text((50, notes_y), "This license is property of the Lakeview City DMV.", fill=grey_mid, font=small_font)
    draw.text((50, notes_y + 22), "Tampering, duplication, or misuse is prohibited by law.", fill=grey_mid, font=small_font)

    # =====================
    # HOLOGRAPHIC DMV SEAL
    # =====================
    seal = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)

    # Holographic rings
    sdraw.ellipse((0, 0, 180, 180), outline=holo1, width=6)
    sdraw.ellipse((10, 10, 170, 170), outline=holo2, width=4)
    sdraw.ellipse((25, 25, 155, 155), outline=holo3, width=3)

    # Text inside seal
    sdraw.text((52, 70), "Lakeview\nCity DMV\nCertified",
               fill=dmv_gold, font=small_font, align="center")

    seal = seal.filter(ImageFilter.GaussianBlur(0.6))
    img.paste(seal, (W - 220, 150), seal)

    # EXPORT
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

            # SEND TO CHANNEL
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

            # SEND DM
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
