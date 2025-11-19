from __future__ import annotations

# --- stdlib ---
import os
import io
import math
from datetime import datetime, timedelta
from threading import Thread

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

def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = [
        "arialbd.ttf" if bold else "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ============================================================
# MESH (SCALE PATTERN)
# ============================================================

def draw_mesh(draw: ImageDraw.ImageDraw, W: int, H: int, alpha: int = 28):
    """Draw soft fish-scale mesh over the whole card."""
    spacing = 46  # tuned to match your reference image
    color = (255, 255, 255, alpha)
    for y in range(0, H + spacing, spacing):
        for x in range(0, W + spacing, spacing):
            # arcs that overlap into a scale pattern
            draw.arc(
                (x - spacing, y - spacing, x + spacing, y + spacing),
                0,
                180,
                fill=color,
                width=2,
            )


# ============================================================
# STAR (BOTTOM-RIGHT SECURITY STAR)
# ============================================================

def draw_star() -> Image.Image:
    """Draw the DMV star watermark like in your reference."""
    size = 110
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    outer_r = 50
    inner_r = 20
    pts = []
    for i in range(16):
        ang = math.radians(i * 22.5)
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        pts.append((x, y))

    d.polygon(pts, fill=(40, 90, 180), outline="white", width=3)
    return img


# ============================================================
# LICENSE IMAGE GENERATOR
# ============================================================

def create_license_image(
    username: str,
    avatar_bytes: bytes,
    display_name: str | None,
    roleplay_name: str | None,
    age: str | int | None,
    address: str | None,
    eye_color: str | None,
    height: str | None,
    issued: datetime,
    expires: datetime,
    lic_num: str,
    license_type: str = "standard",
) -> bytes:
    W, H = 820, 520

    roleplay = str(roleplay_name) if roleplay_name else username
    age_str = "" if age is None else str(age)
    address_str = "" if address is None else str(address)
    eye_str = "" if eye_color is None else str(eye_color)
    height_str = "" if height is None else str(height)

    # Base rounded card
    card = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), 120, fill=255)
    card.putalpha(mask)

    # Background gradient (blue)
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    for y in range(H):
        ratio = y / H
        r = int(150 + 40 * ratio)
        g = int(180 + 50 * ratio)
        b = int(220 + 20 * ratio)
        bgd.line((0, y, W, y), fill=(r, g, b, 255))

    # Mesh (white, blurred)
    mesh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)
    draw_mesh(md, W, H, alpha=32)
    mesh = mesh.filter(ImageFilter.GaussianBlur(0.7))
    bg.alpha_composite(mesh)

    # Header strip (blue or orange) – curved with card
    HEADER_H = 95
    header = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)
    for i in range(HEADER_H):
        if license_type == "provisional":
            # Golden / soft orange gradient
            r1, r2 = 245, 180
            g1, g2 = 160, 120
            b1, b2 = 60, 20
            rr = int(r1 + (r2 - r1) * (i / HEADER_H))
            gg = int(g1 + (g2 - g1) * (i / HEADER_H))
            bb = int(b1 + (b2 - b1) * (i / HEADER_H))
            hd.line((0, i, W, i), fill=(rr, gg, bb, 255))
        else:
            # Standard blue gradient
            shade = int(35 + (60 - 35) * (i / HEADER_H))
            hd.line((0, i, W, i), fill=(shade, 70, 160, 255))

    header_mask = mask.crop((0, 0, W, HEADER_H))
    header.putalpha(header_mask)
    bg.alpha_composite(header, (0, 0))

    # Apply bg + header to card
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    # Title
    if license_type == "provisional":
        title = "LAKEVIEW CITY PROVISIONAL LICENSE"
        title_font = load_font(34, bold=True)
    else:
        title = "LAKEVIEW CITY DRIVER LICENSE"
        title_font = load_font(39, bold=True)

    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) / 2, 24), title, fill="white", font=title_font)

    # Avatar
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))
        m2 = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(m2).rounded_rectangle((0, 0, 200, 200), 42, fill=255)
        av.putalpha(m2)
        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58, 158))
        card.alpha_composite(av, (50, 150))
    except Exception:
        pass

    section = load_font(24, bold=True)
    bold = load_font(22, bold=True)
    normal = load_font(22)
    blue = (50, 110, 200)
    grey = (35, 35, 35)

    # Identity section
    ix, iy = 290, 160
    draw.text((ix, iy), "IDENTITY:", font=section, fill=blue)
    draw.line((ix, iy + 34, ix + 250, iy + 34), fill=blue, width=3)
    iy += 55

    def write_pair(x, y, label, value):
        lw = draw.textlength(label, font=bold)
        draw.text((x, y), label, font=bold, fill=grey)
        draw.text((x + lw + 10, y), str(value), font=normal, fill=grey)

    write_pair(ix, iy, "Name:", roleplay)
    write_pair(ix, iy + 34, "Age:", age_str)
    write_pair(ix, iy + 68, "Address:", address_str)

    # Physical section
    px, py = 550, 160
    draw.text((px, py), "PHYSICAL:", font=section, fill=blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)
    py += 55
    write_pair(px, py, "Eye Color:", eye_str)
    write_pair(px, py + 34, "Height:", height_str)

    # DMV box
    BOX_Y, BOX_H = 360, 140
    box = Image.new("RGBA", (W - 80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle(
        (0, 0, W - 80, BOX_H),
        radius=45,
        fill=(200, 220, 255, 90),
        outline=(80, 140, 255, 180),
        width=3,
    )
    card.alpha_composite(box, (40, BOX_Y))
    draw = ImageDraw.Draw(card)

    draw.text((60, BOX_Y + 15), "DMV INFO:", font=section, fill=blue)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue, width=3)

    uname_font = load_font(24, bold=True)
    uname_w = draw.textlength(username, font=uname_font)
    center_x = 40 + (W - 80) // 2
    draw.text((center_x - uname_w / 2, BOX_Y + 15), username, font=uname_font, fill=grey)

    y2 = BOX_Y + 65
    draw.text((60, y2), "License Class:", font=bold, fill=grey)
    draw.text(
        (245, y2),
        "Provisional" if license_type == "provisional" else "Standard",
        font=normal,
        fill=grey,
    )

    y2 += 38
    draw.text((60, y2), "Issued:", font=bold, fill=grey)
    draw.text((150, y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    draw.text((330, y2), "Expires:", font=bold, fill=grey)
    draw.text((430, y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    # Star in DMV box bottom-right
    star = draw_star()
    card.alpha_composite(star, (W - 150, BOX_Y + 10))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ============================================================
# SEND DM EMBED
# ============================================================

async def send_dm_license(
    discord_id: str,
    img_bytes: bytes,
    filename: str,
    roleplay_name: str | None,
    license_type: str,
    issued: datetime,
    expires: datetime,
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
    rp = roleplay_name or "Citizen"

    if license_type == "provisional":
        embed.description = (
            f"> Greetings, <@{discord_id}>.\n"
            f"> Our services have automatically created your provisional license, this is valid until "
            f"**{expires.strftime('%B %d, %Y at %I:%M %p UTC')}** (<t:{expires_ts}:F>). "
            f"To generate an official license that is permanent, check out "
            f"https://discord.com/channels/1328475009542258688/1437618758440063128.\n\n"
            f"> Please note that violating traffic regulations which equate to you being cited or gathering "
            f"points will result in an immediate removal of this license, it will also entail you to complete "
            f"a formal driving test before receiving an official drivers license.\n\n"
            f"> You have until this provisional license expires to create an official license, not having one "
            f"will get you arrested, we recommend you save this!\n\n"
            f"> Thank you **{rp}** for working with the City of Lakeview\n"
            f"Signed, Department of Motor Vehicles"
        )
    else:
        embed.description = (
            f"> Greetings, <@{discord_id}>.\n"
            f"> Our services have generated your Drivers License, this is permanent. We advise you follow all "
            f"traffic regulations set, gaining a total of 15 points on your license will result in mandatory "
            f"retraining (driving test).\n\n"
            f"> Your license was generated at **{issued.strftime('%B %d, %Y at %I:%M %p UTC')}** "
            f"(<t:{issued_ts}:F>). For any questions, contact the DMV (Department of Motor Vehicles) directly.\n\n"
            f"> Thank you **{rp}** for working with the City of Lakeview\n"
            f"Signed, Department of Motor Vehicles"
        )

    # Show license as embed image via attachment
    embed.set_image(url=f"attachment://{filename}")
    file = discord.File(io.BytesIO(img_bytes), filename=filename)
    await user.send(content=f"<@{discord_id}>", embed=embed, file=file)


# ============================================================
# LOGGING
# ============================================================

async def log_license(discord_id: str, img_bytes: bytes, filename: str):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return
    file = discord.File(io.BytesIO(img_bytes), filename=filename)
    await channel.send(
        content=f"License issued to: <@{discord_id}> (ID: {discord_id})",
        file=file,
    )


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
        avatar_url = data.get("roblox_avatar")
        roleplay = data.get("roleplay_name")
        age = data.get("age")
        addr = data.get("address")
        eye = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")
        license_type = data.get("license_type", "standard")

        if not username or not avatar_url or not discord_id:
            return jsonify({"status": "error", "message": "Missing username/avatar/discord_id"}), 400

        avatar_bytes = requests.get(avatar_url).content

        issued = datetime.utcnow()
        expires = issued + timedelta(days=3 if license_type == "provisional" else 150)

        img_bytes = create_license_image(
            username=username,
            avatar_bytes=avatar_bytes,
            display_name=display,
            roleplay_name=roleplay,
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
                discord_id=discord_id,
                img_bytes=img_bytes,
                filename=filename,
                roleplay_name=roleplay,
                license_type=license_type,
                issued=issued,
                expires=expires,
            )
        )
        bot.loop.create_task(
            log_license(discord_id=discord_id, img_bytes=img_bytes, filename=filename)
        )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print("LICENSE ENDPOINT ERROR:\n", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# BOT STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
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
