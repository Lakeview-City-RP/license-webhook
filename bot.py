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
    grid_color = (225, 230, 240, 80)
    dmv_gold = (220, 180, 80, 230)

    # FONTS
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22, bold=False)
    small_font = load_font(16, bold=False)

    # ================
    # Rounded Card Base
    # ================
    radius = 60
    base = Image.new("RGBA", (W, H), card_bg)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=radius, fill=255)
    img.paste(base, (0, 0), mask)

    # =============
    # HEADER BAR
    # =============
    draw.rounded_rectangle((0, 0, W, 95), radius=60, fill=header_blue)
    header_text = "Lakeview City • Driver’s License"
    tw = draw.textlength(header_text, font=title_font)
    draw.text(((W - tw) / 2, 25), header_text, fill="white", font=title_font)

    # ======================
    # BACKGROUND PATTERN
    # ======================
    for yy in range(110, H, 40):
        for xx in range(0, W, 40):
            draw.rectangle((xx + 10, yy + 10, xx + 26, yy + 26), fill=grid_color)

    # ======================
    # WATERMARK
    # ======================
    wm_txt = "LAKEVIEW"
    wm_font = load_font(120, bold=True)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wm_layer)
    tw = wdraw.textlength(wm_txt, font=wm_font)

    tmp = Image.new("RGBA", (int(tw) + 40, 160), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tmp)
    tdraw.text((20, 0), wm_txt, font=wm_font, fill=(150, 150, 150, 65))
    tmp = tmp.rotate(33, expand=True, resample=Image.BICUBIC)
    tmp = tmp.filter(ImageFilter.GaussianBlur(1.3))

    wm_layer.paste(tmp, (W//2 - tmp.width//2, H//2 - tmp.height//2), tmp)
    img = Image.alpha_composite(img, wm_layer)
    draw = ImageDraw.Draw(img)

    # =============
    # AVATAR
    # =============
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((200, 200))
        amask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(amask).rounded_rectangle((0, 0, 200, 200), radius=35, fill=255)
        avatar.putalpha(amask)
        img.paste(avatar, (45, 135), avatar)
    except:
        pass

    # ====================================================
    # INFO COLUMNS (Identity + Physical)
    # ====================================================
    left_x = 280
    y = 145
    gap = 36

    draw.text((left_x, y), f"@{username}", fill=blue_accent, font=label_font)
    y += gap

    def field(label, value, y):
        draw.text((left_x, y), label, font=label_font, fill=grey_dark)
        lw = draw.textlength(label, font=label_font)
        draw.text((left_x + lw + 8, y), value or "N/A", font=value_font, fill=grey_mid)

    # Identity
    field("Name:", roleplay_name or username, y); y += gap
    field("Age:", age, y); y += gap
    field("Address:", address, y)

    # Physical Info
    rx = 280
    ry = 290
    field("Eye Color:", eye_color, ry); ry += gap
    field("Height:", height, ry)

    # ===========================
    # DMV INFO COLUMN (Left-Aligned)
    # ===========================
    dmv_y = 350
    draw.text((50, dmv_y), f"License: {lic_num}", fill=grey_dark, font=label_font)
    draw.text((50, dmv_y + 32), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)
    draw.text((50, dmv_y + 64), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)

    # =============
    # DMV NOTES
    # =============
    ny = 440
    draw.text((50, ny), "This license is property of the Lakeview City DMV.", fill=grey_mid, font=small_font)
    draw.text((50, ny + 22), "Tampering, duplication, or misuse is prohibited by law.", fill=grey_mid, font=small_font)

    # =============
    # DMV GOLD SEAL
    # =============
    seal = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    sdraw.ellipse((0, 0, 160, 160), outline=(220, 180, 80, 255), width=5)
    sdraw.ellipse((20, 20, 140, 140), outline=(220, 180, 80, 160), width=2)
    sdraw.text((45, 60), "Lakeview\nCity DMV\nCertified", fill=dmv_gold, font=small_font, align="center")

    seal = seal.filter(ImageFilter.GaussianBlur(0.8))
    img.paste(seal, (W - 200, 170), seal)

    # =============
    # EXPORT PNG
    # =============
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
