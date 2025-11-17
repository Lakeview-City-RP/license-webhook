from __future__ import annotations

# --- stdlib ---
import os, io
from datetime import datetime, timedelta
from threading import Thread

# --- third-party ---
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py ---
import discord
from discord.ext import commands


# ==========================
#   TOKEN / DISCORD SETUP
# ==========================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token missing.")

PREFIX = "?"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)


# ==========================
#      FONT LOADING
# ==========================

def load_font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf"
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ==========================
#   LICENSE IMAGE BUILDER
# ==========================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):

    W, H = 820, 520

    # ===== Base Card =====
    # Card with rounded mask
    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=70, fill=255)
    base.putalpha(mask)

    card = base.copy()
    draw = ImageDraw.Draw(card)

    # ===== Colors =====
    grey_dark = (40, 40, 40)
    grey_mid = (80, 80, 80)
    blue_accent = (60, 120, 220)
    mesh_color = (180, 200, 230, 60)

    # ===== Fonts =====
    title_font = load_font(42, bold=True)
    section_font = load_font(24, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22, bold=False)
    wm_font = load_font(110, bold=True)
    small_font = load_font(16)

    # ===== HEADER BAR =====
    header = Image.new("RGBA", (W, 95), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)
    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))
    card = Image.alpha_composite(card, header)

    # Title
    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 25), title, font=title_font, fill="white")

    # ===== MESH (CLIPPED) =====
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)
    spacing = 30

    for y in range(130, H - 20, spacing):
        for x in range(0, W, spacing):
            md.line((x, y, x + 15, y + 15), fill=mesh_color, width=2)
            md.line((x + 15, y, x, y + 15), fill=mesh_color, width=2)

    mesh.putalpha(mask)
    mesh = mesh.filter(ImageFilter.GaussianBlur(1))
    card = Image.alpha_composite(card, mesh)

    # ===== WATERMARK =====
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    wm_text = "LAKEVIEW"
    tw = wd.textlength(wm_text, font=wm_font)

    t = Image.new("RGBA", (int(tw) + 40, 200), (0, 0, 0, 0))
    td = ImageDraw.Draw(t)
    td.text((20, 0), wm_text, font=wm_font, fill=(140, 140, 140, 35))
    t = t.rotate(29, expand=True).filter(ImageFilter.GaussianBlur(1.5))
    wm.paste(t, (W//2 - t.width//2, H//3), t)

    wm.putalpha(mask)
    card = Image.alpha_composite(card, wm)
    draw = ImageDraw.Draw(card)

    # ===== AVATAR =====
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((200, 200))
        av_mask = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(av_mask).rounded_rectangle((0, 0, 200, 200), 35, fill=255)
        av.putalpha(av_mask)
        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.paste(shadow, (58, 153), shadow)
        card.paste(av, (50, 145), av)
    except Exception as e:
        print("Avatar error:", e)

    # ===== SECTION HEADERS =====
    ix, iy = 300, 150
    px, py = 550, 150

    draw.text((ix, iy), "IDENTITY", section_font, fill=blue_accent)
    draw.line((ix, iy+36, ix+240, iy+36), fill=blue_accent, width=3)

    draw.text((px, py), "PHYSICAL", section_font, fill=blue_accent)
    draw.line((px, py+36, px+240, py+36), fill=blue_accent, width=3)

    # Identity fields
    iy += 55
    draw.text((ix, iy), "Name:", label_font, fill=grey_dark)
    draw.text((ix+120, iy), roleplay_name or username, value_font, fill=grey_mid); iy += 32

    draw.text((ix, iy), "Age:", label_font, fill=grey_dark)
    draw.text((ix+120, iy), age, value_font, fill=grey_mid); iy += 32

    draw.text((ix, iy), "Address:", label_font, fill=grey_dark)
    draw.text((ix+120, iy), address, value_font, fill=grey_mid)

    # Physical
    py += 55
    draw.text((px, py), "Eye Color:", label_font, fill=grey_dark)
    draw.text((px+140, py), eye_color, value_font, fill=grey_mid); py += 32

    draw.text((px, py), "Height:", label_font, fill=grey_dark)
    draw.text((px+140, py), height, value_font, fill=grey_mid)

    # ===== DMV INFO =====
    BOX_Y = 362
    BOX_H = 145

    box = Image.new("RGBA", (W-80, BOX_H), (0, 0, 0, 0))
    bx = ImageDraw.Draw(box)
    bx.rounded_rectangle((0, 0, W-80, BOX_H), 30, fill=(200,220,255,110),
                         outline=(80,140,255,180), width=3)
    card.paste(box, (40, BOX_Y), box)

    draw.text((60, BOX_Y+12), "DMV INFO", section_font, fill=blue_accent)
    draw.line((60, BOX_Y+44, 300, BOX_Y+44), fill=blue_accent, width=3)

    y2 = BOX_Y + 65

    draw.text((60, y2), "License Class:", label_font, fill=grey_dark)
    draw.text((240, y2), "Standard", value_font, fill=grey_mid); y2 += 30

    draw.text((60, y2), "Issued:", label_font, fill=grey_dark)
    draw.text((240, y2), issued.strftime("%Y-%m-%d"), value_font, fill=grey_mid); y2 += 30

    draw.text((60, y2), "Expires:", label_font, fill=grey_dark)
    draw.text((240, y2), expires.strftime("%Y-%m-%d"), value_font, fill=grey_mid)

    # ===== DIAMOND BADGE =====
    badge = Image.new("RGBA", (95, 95), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    diamond = [(47,0),(94,47),(47,94),(0,47)]
    bd.polygon(diamond, fill=(30,60,140,255), outline=(255,255,255,200), width=3)
    bd.text((27,28), "DMV", font=label_font, fill="white")
    bd.text((22,55), "CERT", font=small_font, fill="white")
    badge = badge.filter(ImageFilter.GaussianBlur(0.5))

    card.paste(badge, (W-150, BOX_Y+22), badge)

    # ===== EXPORT =====
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# ==========================
#       DISCORD SENDER
# ==========================

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
            file=file
        )

    if discord_id:
        try:
            user = await bot.fetch_user(int(discord_id))
            if user:
                dm = discord.Embed(
                    title="Your Lakeview City Driver’s License",
                    color=0x757575
                )
                dm.set_image(url=f"attachment://{filename}")
                await user.send(
                    embed=dm,
                    file=discord.File(io.BytesIO(img_data), filename=filename)
                )
        except Exception as e:
            print("[DM Error]", e)


# ==========================
#         FLASK API
# ==========================

app = Flask(__name__)


@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json
        print("\n======== /license HIT ========")
        print("RAW BODY:", request.data)
        print("PARSED JSON:", data)

        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")
        roleplay_name = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye_color = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")

        print("username =", username)
        print("avatar_url =", avatar_url)

        if not username or not avatar_url:
            return jsonify({"status": "error", "message": "Missing username/avatar"}), 400

        avatar_bytes = requests.get(avatar_url).content
        print("Downloaded avatar:", len(avatar_bytes), "bytes")

        issued = datetime.utcnow()
        expires = issued + timedelta(days=30 * 5)  # approx 5 months

        img = create_license_image(
            username, avatar_bytes, roleplay_name, age, address,
            eye_color, height, issued, expires, username
        )

        bot.loop.create_task(
            send_license_to_discord(img, f"{username}_license.png", discord_id)
        )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print("\n--- EXCEPTION ---")
        print(traceback.format_exc())
        print("--- END ---")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================
#          COMMANDS
# ==========================

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency * 1000)}ms`")


# ==========================
#           RUN
# ==========================

def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Starting Flask server...")
    app.run(host="0.0.0.0", port=8080)
