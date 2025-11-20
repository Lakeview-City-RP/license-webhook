from __future__ import annotations

# ============================================================
# IMPORTS
# ============================================================

import os
import io
import math
from datetime import datetime, timedelta
from threading import Thread

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

import discord
from discord.ext import commands

# ============================================================
# CONFIG
# ============================================================

# Discord token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN and os.path.exists("token.txt"):
    TOKEN = open("token.txt", "r").read().strip()

if not TOKEN:
    raise RuntimeError("Discord token missing.")

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
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ============================================================
# FONT LOADING
# ============================================================

def load_font(size: int, bold: bool = False):
    paths = [
        "arialbd.ttf" if bold else "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()

# ============================================================
# PERFECT MESH (REFERENCE MATCH)
# ============================================================

def draw_mesh(draw: ImageDraw.ImageDraw, W: int, H: int):
    spacing = 46
    color = (255, 255, 255, 33)
    for y in range(0, H + spacing, spacing):
        for x in range(0, W + spacing, spacing):
            draw.arc(
                (x - spacing, y - spacing, x + spacing, y + spacing),
                0,
                180,
                fill=color,
                width=2,
            )

# ============================================================
# STAR
# ============================================================

def draw_star():
    size = 110
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    d = ImageDraw.Draw(img)

    cx = cy = size // 2
    outer = 50
    inner = 20
    pts = []
    for i in range(16):
        ang = math.radians(i * 22.5)
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

    d.polygon(pts, fill=(40,90,180), outline="white", width=3)
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    return img

# ============================================================
# LICENSE GENERATOR
# ============================================================

def create_license_image(
    username,
    avatar_bytes,
    display,
    roleplay,
    age,
    address,
    eye_color,
    height,
    issued,
    expires,
    lic_num,
    license_type="standard",
):
    W, H = 820, 520

    roleplay = roleplay or username
    age_str = "" if age is None else str(age)
    address_str = "" if address is None else str(address)
    eye_str = "" if eye_color is None else str(eye_color)
    height_str = "" if height is None else str(height)

    # Base rounded card
    base = Image.new("RGBA", (W, H), (255,255,255,0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,W,H), 120, fill=255)
    base.putalpha(mask)

    # Background gradient
    bg = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(bg)

    for y in range(H):
        ratio = y / H
        r = int(150 + 40 * ratio)
        g = int(180 + 50 * ratio)
        b = int(220 + 20 * ratio)
        gd.line((0,y,W,y), fill=(r,g,b))

    # Header
    HEADER_H = 95
    header = Image.new("RGBA", (W, HEADER_H), (0,0,0,0))
    hd = ImageDraw.Draw(header)

    if license_type == "provisional":
        # Soft gold/orange fix (Option B)
        for i in range(HEADER_H):
            ratio = i / HEADER_H
            rr = int(240 - 40 * ratio)
            gg = int(180 - 70 * ratio)
            bb = int(90 - 60 * ratio)
            hd.line((0,i,W,i), fill=(rr,gg,bb))
    else:
        # Standard blue header
        for i in range(HEADER_H):
            shade = int(35 + (60 - 35) * (i / HEADER_H))
            hd.line((0,i,W,i), fill=(shade,70,160))

    header.putalpha(mask.crop((0,0,W,HEADER_H)))
    bg.alpha_composite(header, (0,0))

    # Mesh (placed ABOVE header)
    mesh = Image.new("RGBA", (W, H), (0,0,0,0))
    md = ImageDraw.Draw(mesh)
    draw_mesh(md, W, H)
    mesh = mesh.filter(ImageFilter.GaussianBlur(0.6))
    bg.alpha_composite(mesh)

    # Apply background
    card = Image.alpha_composite(base, bg)
    d = ImageDraw.Draw(card)

    # Title
    if license_type == "provisional":
        title = "LAKEVIEW CITY PROVISIONAL LICENSE"
        title_font = load_font(30, True)
    else:
        title = "LAKEVIEW CITY DRIVER LICENSE"
        title_font = load_font(39, True)

    tw = d.textlength(title, font=title_font)
    d.text(((W - tw) / 2, 24), title, fill="white", font=title_font)

    # Avatar
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200,200))
        m2 = Image.new("L", (200,200), 0)
        ImageDraw.Draw(m2).rounded_rectangle((0,0,200,200), 42, fill=255)
        av.putalpha(m2)
        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58,158))
        card.alpha_composite(av, (50,150))
    except:
        pass

    # Text styles
    sec = load_font(24, True)
    bold = load_font(22, True)
    normal = load_font(22)
    blue = (50,110,200)
    grey = (35,35,35)

    # Identity
    ix, iy = 290, 160
    d.text((ix,iy), "IDENTITY:", font=sec, fill=blue)
    d.line((ix,iy+34, ix+250, iy+34), fill=blue, width=3)
    iy += 55

    def pair(x, y, label, value):
        lw = d.textlength(label, font=bold)
        d.text((x,y), label, font=bold, fill=grey)
        d.text((x+lw+10, y), value, font=normal, fill=grey)

    pair(ix,iy, "Name:", roleplay)
    pair(ix,iy+34, "Age:", age_str)
    pair(ix,iy+68, "Address:", address_str)

    # Physical
    px, py = 550, 160
    d.text((px,py), "PHYSICAL:", font=sec, fill=blue)
    d.line((px,py+34, px+250, py+34), fill=blue, width=3)
    py += 55

    pair(px,py, "Eye Color:", eye_str)
    pair(px,py+34, "Height:", height_str)

    # DMV box
    BOX_Y = 360
    BOX_H = 140
    box = Image.new("RGBA", (W-80, BOX_H), (0,0,0,0))
    bd = ImageDraw.Draw(box)

    bd.rounded_rectangle(
        (0,0,W-80,BOX_H),
        radius=45,
        fill=(200,220,255,80),
        outline=(80,140,255,180),
        width=3,
    )

    card.alpha_composite(box, (40, BOX_Y))
    d = ImageDraw.Draw(card)

    d.text((60,BOX_Y+15), "DMV INFO:", font=sec, fill=blue)
    d.line((60,BOX_Y+47,300,BOX_Y+47), fill=blue, width=3)

    uname_font = load_font(24, True)
    uname_w = d.textlength(username, font=uname_font)
    center_x = 40 + (W-80)//2
    d.text((center_x - uname_w/2, BOX_Y+15), username, font=uname_font, fill=grey)

    y2 = BOX_Y + 65
    d.text((60,y2), "License Class:", font=bold, fill=grey)
    d.text(
        (245,y2),
        "Provisional" if license_type=="provisional" else "Standard",
        font=normal,
        fill=grey
    )

    y2 += 38
    d.text((60,y2), "Issued:", font=bold, fill=grey)
    d.text((150,y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    d.text((330,y2), "Expires:", font=bold, fill=grey)
    d.text((430,y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    # Star
    star = draw_star()
    card.alpha_composite(star, (W-150, BOX_Y+10))

    # Export
    buf = io.BytesIO()
    card.save(buf, "PNG")
    buf.seek(0)
    return buf.getvalue()

# ============================================================
# SEND DM LICENSE
# ============================================================

async def send_dm_license(
    discord_id, img_bytes, filename, roleplay, license_type, issued, expires
):
    user = await bot.fetch_user(int(discord_id))
    guild = bot.get_guild(SERVER_ID)

    embed = discord.Embed(
        title=(
            "Your Provisional License has been generated!"
            if license_type == "provisional"
            else "Your Driving License has been generated!"
        ),
        color=EMBED_COLOR,
    )

    embed.set_thumbnail(url=DM_THUMBNAIL)
    embed.set_footer(
        text=EMBED_FOOTER,
        icon_url=guild.icon.url if guild and guild.icon else None,
    )

    issued_ts = int(issued.timestamp())
    expires_ts = int(expires.timestamp())
    rp = roleplay or username

    if license_type == "provisional":
        embed.description = (
            f"> Greetings, <@{discord_id}>.\n"
            f"> Your provisional license is valid until "
            f"**{expires.strftime('%B %d, %Y at %I:%M %p UTC')}** (<t:{expires_ts}:F>).\n"
            f"> Permanent license: https://discord.com/channels/1328475009542258688/1437618758440063128\n\n"
            f"> Violations void this license and require a driving test.\n\n"
            f"> Thank you **{rp}**.\nSigned, Department of Motor Vehicles"
        )
    else:
        embed.description = (
            f"> Greetings, <@{discord_id}>.\n"
            f"> Permanent license issued at "
            f"**{issued.strftime('%B %d, %Y at %I:%M %p UTC')}** (<t:{issued_ts}:F>).\n"
            f"> Accumulating 15 points requires retraining.\n\n"
            f"> Thank you **{rp}**.\nSigned, Department of Motor Vehicles"
        )

    embed.set_image(url=f"attachment://{filename}")
    file = discord.File(io.BytesIO(img_bytes), filename=filename)
    await user.send(content=f"<@{discord_id}>", embed=embed, file=file)

# ============================================================
# LOG LICENSE
# ============================================================

async def log_license(discord_id, img_bytes, filename):
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if not ch:
        return

    f = discord.File(io.BytesIO(img_bytes), filename=filename)
    await ch.send(
        content=f"License issued to <@{discord_id}> (ID: {discord_id})",
        file=f
    )

# ============================================================
# FLASK ENDPOINT
# ============================================================

app = Flask(__name__)

@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json
        if not data:
            return jsonify({"status":"error","message":"Invalid JSON"}), 400

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")
        discord_id = data.get("discord_id")

        if not username or not avatar_url or not discord_id:
            return jsonify({"status":"error","message":"Missing fields"}), 400

        roleplay = data.get("roleplay_name") or username
        display = data.get("roblox_display")
        age = data.get("age")
        addr = data.get("address")
        eye = data.get("eye_color")
        height = data.get("height")
        license_type = data.get("license_type", "standard")

        issued = datetime.utcnow()
        expires = issued + timedelta(
            days=3 if license_type == "provisional" else 150
        )

        avatar_bytes = requests.get(avatar_url).content

        img_bytes = create_license_image(
            username=username,
            avatar_bytes=avatar_bytes,
            display=display,
            roleplay=roleplay,
            age=age,
            address=addr,
            eye_color=eye,
            height=height,
            issued=issued,
            expires=expires,
            lic_num=username,
            license_type=license_type,
        )

        filename = f"{username}_license.png"

        bot.loop.create_task(
            send_dm_license(
                discord_id, img_bytes, filename, roleplay, license_type, issued, expires
            )
        )

        bot.loop.create_task(
            log_license(discord_id, img_bytes, filename)
        )

        return jsonify({"status":"ok"}), 200

    except Exception as e:
        import traceback
        print("LICENSE ERROR:\n", traceback.format_exc())
        return jsonify({"status":"error","message":str(e)}), 500

# ============================================================
# BOT STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

async def setup_hook():
    pass

bot.setup_hook = setup_hook

# ============================================================
# RUN BOT + FLASK
# ============================================================

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
