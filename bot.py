from __future__ import annotations

# --- stdlib ---
import os
import io
from datetime import datetime, timedelta
from threading import Thread
import math

# --- third-party ---
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py ---
import discord
from discord.ext import commands


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found!")

PREFIX = "?"

SERVER_ID = 1328475009542258688
LOG_CHANNEL_ID = 1436890841703645285

DM_THUMBNAIL = (
    "https://media.discordapp.net/attachments/1377401295220117746/"
    "1437245076945375393/WHITELISTED_NO_BACKGROUND.png?format=png&quality=lossless"
)
EMBED_COLOR = 0x757575
EMBED_FOOTER = "Lakeview City Whitelisted Automation Services"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
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
# LICENSE IMAGE GENERATOR
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
    license_type="standard"
):
    W, H = 820, 520

    # Clean values
    roleplay_name_str = str(roleplay_name) if roleplay_name else username

    # Base card (rounded)
    card = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    full_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(full_mask).rounded_rectangle((0, 0, W, H), 120, fill=255)
    card.putalpha(full_mask)

    # Background gradient
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    for y in range(H):
        ratio = y / H
        r = int(150 + 40 * ratio)
        g = int(180 + 50 * ratio)
        b = int(220 + 20 * ratio)
        bgd.line((0, y, W, y), fill=(r, g, b, 255))

    # Background waves
    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)
    for x in range(0, W, 40):
        for y in range(0, H, 40):
            wd.arc((x, y, x + 80, y + 80), 0, 180, fill=(255, 255, 255, 25), width=2)
    wave = wave.filter(ImageFilter.GaussianBlur(1.4))
    bg.alpha_composite(wave)

    # HEADER
    HEADER_H = 95
    header = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(HEADER_H):
        if license_type == "provisional":
            # Soft Orange
            r1, r2 = 245, 160
            g1, g2 = 160, 100
            b1, b2 = 60, 25
            rr = int(r1 + (r2 - r1) * (i / HEADER_H))
            gg = int(g1 + (g2 - g1) * (i / HEADER_H))
            bb = int(b1 + (b2 - b1) * (i / HEADER_H))
            hd.line((0, i, W, i), fill=(rr, gg, bb))
        else:
            # Blue gradient
            shade = int(35 + (60 - 35) * (i / HEADER_H))
            hd.line((0, i, W, i), fill=(shade, 70, 160))

    header.putalpha(full_mask.crop((0, 0, W, HEADER_H)))
    card.alpha_composite(header, (0, 0))
    draw = ImageDraw.Draw(card)

    # TITLE
    if license_type == "provisional":
        title = "LAKEVIEW CITY PROVISIONAL LICENSE"
        title_font = load_font(34, bold=True)
    else:
        title = "LAKEVIEW CITY DRIVER LICENSE"
        title_font = load_font(39, bold=True)

    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 24), title, fill="white", font=title_font)

    # AVATAR
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

    section = load_font(24, bold=True)
    bold = load_font(22, bold=True)
    normal = load_font(22)
    blue = (50, 110, 200)
    grey = (35, 35, 35)

    # IDENTITY SECTION
    ix, iy = 290, 160
    draw.text((ix, iy), "IDENTITY:", font=section, fill=blue)
    draw.line((ix, iy + 34, ix + 250, iy + 34), fill=blue, width=3)
    iy += 55

    def write_pair(x, y, label, value):
        lw = draw.textlength(label, font=bold)
        draw.text((x, y), label, font=bold, fill=grey)
        draw.text((x + lw + 10, y), str(value), font=normal, fill=grey)

    write_pair(ix, iy, "Name:", roleplay_name_str)
    write_pair(ix, iy + 34, "Age:", age)
    write_pair(ix, iy + 68, "Address:", address)

    # PHYSICAL SECTION
    px, py = 550, 160
    draw.text((px, py), "PHYSICAL:", font=section, fill=blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)
    py += 55
    write_pair(px, py, "Eye Color:", eye_color)
    write_pair(px, py + 34, "Height:", height)

    # DMV INFO BOX
    BOX_Y, BOX_H = 360, 140
    box = Image.new("RGBA", (W - 80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle(
        (0, 0, W - 80, BOX_H),
        radius=45,
        fill=(200, 220, 255, 90),
        outline=(80, 140, 255, 180),
        width=3
    )
    card.alpha_composite(box, (40, BOX_Y))
    draw = ImageDraw.Draw(card)

    draw.text((60, BOX_Y + 15), "DMV INFO:", font=section, fill=blue)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue, width=3)

    # Center username
    uname_font = load_font(24, bold=True)
    uname_w = draw.textlength(username, font=uname_font)
    center_x = 40 + (W - 80) // 2
    draw.text((center_x - uname_w / 2, BOX_Y + 15), username, font=uname_font, fill=grey)

    # DMV DETAILS
    y2 = BOX_Y + 65
    draw.text((60, y2), "License Class:", font=bold, fill=grey)
    draw.text((245, y2), "Provisional" if license_type == "provisional" else "Standard",
              font=normal, fill=grey)

    y2 += 38
    draw.text((60, y2), "Issued:", font=bold, fill=grey)
    draw.text((150, y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    draw.text((330, y2), "Expires:", font=bold, fill=grey)
    draw.text((430, y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ============================================================
# SEND DM EMBED
# ============================================================

async def send_dm_license(discord_id, img_bytes, filename, roleplay_name, license_type, issued, expires):
    user = await bot.fetch_user(int(discord_id))
    guild = bot.get_guild(SERVER_ID)

    embed = discord.Embed(
        title=(
            "Your Provisional License has been generated!"
            if license_type == "provisional"
            else "Your Driving License has been generated!"
        ),
        color=EMBED_COLOR
    )

    embed.set_thumbnail(url=DM_THUMBNAIL)
    embed.set_footer(text=EMBED_FOOTER)

    if guild and guild.icon:
        embed.set_image(url=guild.icon.url)

    issued_ts = int(issued.timestamp())
    expires_ts = int(expires.timestamp())

    # --------------------------------------------------------
    # PROVISIONAL DM CONTENT
    # --------------------------------------------------------
    if license_type == "provisional":
        embed.description = (
            f"> Greetings, <@{discord_id}>.\n"
            f"> Our services have automatically created your provisional license, this is valid until "
            f"**{expires.strftime('%B %d, %Y at %I:%M %p UTC')}** (<t:{expires_ts}:F>).\n"
            f"> To generate an official license that is permanent, check out "
            f"https://discord.com/channels/1328475009542258688/1437618758440063128.\n\n"
            f"> Please note that violating traffic regulations which equate to you being cited or gathering points "
            f"will result in an immediate removal of this license, and will require you to complete a formal driving test "
            f"before receiving an official drivers license.\n\n"
            f"> You have until this provisional license expires to create an official license. Not having one will get you arrested.\n\n"
            f"> Thank you **{roleplay_name}** for working with the City of Lakeview.\n"
            f"Signed, Department of Motor Vehicles"
        )

    # --------------------------------------------------------
    # STANDARD DM CONTENT
    # --------------------------------------------------------
    else:
        embed.description = (
            f"> Greetings, <@{discord_id}>.\n"
            f"> Our services have generated your Drivers License, this is permanent. "
            f"We advise you follow all traffic regulations set — gaining a total of 15 points on your license "
            f"will result in mandatory retraining (driving test).\n\n"
            f"> Your license was generated at **{issued.strftime('%B %d, %Y at %I:%M %p UTC')}** "
            f"(<t:{issued_ts}:F>).\n\n"
            f"> Thank you **{roleplay_name}** for working with the City of Lakeview.\n"
            f"Signed, Department of Motor Vehicles"
        )

    file = discord.File(io.BytesIO(img_bytes), filename=filename)
    await user.send(content=f"<@{discord_id}>", embed=embed, file=file)


# ============================================================
# LOG MESSAGE
# ============================================================

async def log_license(discord_id):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"License issued to: <@{discord_id}>")


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

        # "standard" or "provisional"
        license_type = data.get("license_type", "standard")

        if not username or not avatar:
            return jsonify({"status": "error", "message": "Missing username/avatar"}), 400

        avatar_bytes = requests.get(avatar).content

        # Expiration logic
        issued = datetime.utcnow()
        expires = issued + timedelta(days=3 if license_type == "provisional" else 150)

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
            username,
            license_type=license_type
        )

        filename = f"{username}_license.png"

        bot.loop.create_task(
            send_dm_license(discord_id, img, filename, roleplay, license_type, issued, expires)
        )
        bot.loop.create_task(log_license(discord_id))

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# BOT STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
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
