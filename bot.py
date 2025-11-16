from __future__ import annotations

# --- stdlib ---
import os, io, json
from datetime import datetime
from threading import Thread

# --- third-party ---
import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify, send_file, render_template_string

# --- discord.py ---
import discord
from discord.ext import commands

# ======================================================
#  GLOBAL IN-MEMORY LICENSE STORAGE (Option A)
# ======================================================

LICENSE_STORE = {}  # { license_id: { data… , "image": bytes } }

# ======================================================
#  ENVIRONMENT
# ======================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token missing!")

PREFIX = "?"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

LOOKUP_BASE = "https://license-webhook.onrender.com/lookup/"


# ======================================================
#  FONT LOADER
# ======================================================

def load_font(size: int, bold: bool = False):
    paths = [
        "arialbd.ttf" if bold else "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass

    return ImageFont.load_default()


# ======================================================
#  BARCODE GENERATOR
# ======================================================

def generate_barcode(text: str, width=260, height=70):
    import random
    seed = sum(ord(c) for c in text)
    random.seed(seed)

    img = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(img)

    x = 10
    while x < width - 10:
        bar_w = random.choice([2, 3, 4])
        bar_h = random.randint(int(height * 0.65), height - 5)
        d.rectangle((x, height - bar_h, x + bar_w, height), fill=0)
        x += bar_w + random.choice([1, 2, 3])

    return img.convert("RGBA")


# ======================================================
#  LICENSE IMAGE GENERATOR
# ======================================================

def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_id):
    W, H = 820, 520

    # ---- curved mask ----
    card = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    mask = Image.new("L", (W, H))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=70, fill=255)
    card.putalpha(mask)

    draw = ImageDraw.Draw(card)

    # ---- colors ----
    header_blue = (35, 70, 140)
    grey_dark = (40, 40, 40)
    grey_mid = (75, 75, 75)
    blue_accent = (50, 110, 200)
    mesh_color = (200, 200, 215, 50)
    box_bg = (200, 220, 255, 100)
    box_border = (80, 140, 255, 180)
    dmv_gold = (225, 190, 90)

    # ---- fonts ----
    title_font = load_font(42, bold=True)
    section_font = load_font(24, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22)
    small_font = load_font(16)
    wm_font = load_font(110, bold=True)

    # ======================================================
    #  HEADER GRADIENT
    # ======================================================
    header = Image.new("RGBA", (W, 95))
    hd = ImageDraw.Draw(header)

    for i in range(95):
        shade = int(35 + (60 - 35) * (i / 95))
        hd.line((0, i, W, i), fill=(shade, 70, 160))

    header.putalpha(mask)
    card.paste(header, (0, 0), header)

    title = "LAKEVIEW CITY DRIVER LICENSE"
    tw = draw.textlength(title, font=title_font)
    draw.text(((W - tw) // 2, 25), title, fill="white", font=title_font)

    # ======================================================
    #  BACKGROUND X-PATTERN
    # ======================================================
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

    # ======================================================
    #  WATERMARK
    # ======================================================
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wmd = ImageDraw.Draw(wm_layer)

    wm_text = "LAKEVIEW"
    tw = wmd.textlength(wm_text, font=wm_font)
    timg = Image.new("RGBA", (int(tw) + 40, 200), (0, 0, 0, 0))
    td = ImageDraw.Draw(timg)
    td.text((20, 0), wm_text, font=wm_font, fill=(150, 150, 150, 35))

    timg = timg.rotate(28, expand=True)
    timg = timg.filter(ImageFilter.GaussianBlur(1.2))

    wm_layer.paste(timg, (W // 2 - timg.width // 2, H // 3), timg)
    wm_layer.putalpha(mask)
    card = Image.alpha_composite(card, wm_layer)
    draw = ImageDraw.Draw(card)

    # ======================================================
    #  AVATAR
    # ======================================================
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))

        mask_av = Image.new("L", (200, 200))
        ImageDraw.Draw(mask_av).rounded_rectangle((0, 0, 200, 200),
                                                  radius=35, fill=255)
        av.putalpha(mask_av)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.paste(shadow, (58, 153), shadow)
        card.paste(av, (50, 145), av)
    except Exception as e:
        print("[Avatar Error]", e)

    # ======================================================
    #  IDENTITY & PHYSICAL
    # ======================================================

    ix, iy = 300, 150
    px, py = 550, 150

    # Identity header
    draw.text((ix, iy), "IDENTITY", font=section_font, fill=blue_accent)
    draw.line((ix, iy + 34, ix + 240), fill=blue_accent, width=3)

    # Physical header
    draw.text((px, py), "PHYSICAL", font=section_font, fill=blue_accent)
    draw.line((px, py + 34, px + 240), fill=blue_accent, width=3)

    iy += 55
    draw.text((ix, iy), "Name:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), roleplay_name or username,
              font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Age:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), age, font=value_font, fill=grey_mid)
    iy += 32

    draw.text((ix, iy), "Address:", font=label_font, fill=grey_dark)
    draw.text((ix + 120, iy), address, font=value_font, fill=grey_mid)

    py += 55
    draw.text((px, py), "Eye Color:", font=label_font, fill=grey_dark)
    draw.text((px + 140, py), eye_color, font=value_font, fill=grey_mid)
    py += 32

    draw.text((px, py), "Height:", font=label_font, fill=grey_dark)
    draw.text((px + 140, py), height, font=value_font, fill=grey_mid)

    # ======================================================
    #  DMV INFO BOX
    # ======================================================
    BOX_Y = 350
    BOX_H = 150

    box = Image.new("RGBA", (W - 80, BOX_H))
    bd = ImageDraw.Draw(box)

    bd.rounded_rectangle((0, 0, W - 80, BOX_H), radius=35,
                         fill=box_bg, outline=box_border, width=3)

    card.paste(box, (40, BOX_Y), box)
    draw = ImageDraw.Draw(card)

    draw.text((60, BOX_Y + 15), "DMV INFO",
              font=section_font, fill=blue_accent)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47),
              fill=blue_accent, width=3)

    y2 = BOX_Y + 60
    draw.text((60, y2), "License Class: Standard",
              font=label_font, fill=grey_dark)
    y2 += 30
    draw.text((60, y2), f"Issued: {issued.strftime('%Y-%m-%d')}",
              font=label_font, fill=grey_dark)
    y2 += 30
    draw.text((60, y2), f"Expires: {expires.strftime('%Y-%m-%d')}",
              font=label_font, fill=grey_dark)

    # ======================================================
    #  QR CODE
    # ======================================================
    try:
        qr_link = LOOKUP_BASE + lic_id
        qr = qrcode.QRCode(box_size=3, border=1)
        qr.add_data(qr_link)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black",
                               back_color="white").convert("RGBA")
        qr_img = qr_img.resize((110, 110))
        card.paste(qr_img, (W - 240, BOX_Y + 20), qr_img)
    except Exception as e:
        print("[QR ERROR]", e)

    # ======================================================
    #  DMV SHIELD BADGE
    # ======================================================
    shield = Image.new("RGBA", (110, 110))
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

    # ======================================================
    #  BARCODE
    # ======================================================
    try:
        barcode_img = generate_barcode(lic_id)
        barcode_img = barcode_img.resize((180, 60))
        card.paste(barcode_img, (W - 330, BOX_Y + 65), barcode_img)
    except Exception as e:
        print("[Barcode Error]", e)

    # ======================================================
    #  EXPORT PNG
    # ======================================================
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ======================================================
#  DISCORD SEND
# ======================================================

async def send_license_to_discord(img_data, filename, discord_id):
    await bot.wait_until_ready()

    file = discord.File(io.BytesIO(img_data), filename=filename)

    channel = bot.get_channel(1436890841703645285)
    if channel:
        embed = discord.Embed(title="Lakeview City Roleplay Driver’s License",
                              color=0x757575)
        embed.set_image(url=f"attachment://{filename}")
        await channel.send(
            content=f"<@{discord_id}> Your license has been issued!",
            embed=embed, file=file
        )

    # DM copy
    try:
        user = await bot.fetch_user(int(discord_id))
        dm = discord.Embed(title="Your Lakeview City Driver’s License",
                           color=0x757575)
        dm.set_image(url=f"attachment://{filename}")
        await user.send(embed=dm, file=discord.File(io.BytesIO(img_data),
                                                    filename=filename))
    except:
        pass


# ======================================================
#  FLASK APP
# ======================================================

app = Flask(__name__)


@app.route("/license", methods=["POST"])
def api_license():
    try:
        data = request.json or {}

        username = data.get("roblox_username")
        avatar_url = data.get("roblox_avatar")
        role = data.get("roleplay_name")
        age = data.get("age")
        address = data.get("address")
        eye = data.get("eye_color")
        height = data.get("height")
        discord_id = data.get("discord_id")
        license_id = data.get("license_id") or username

        if not username or not avatar_url:
            return jsonify({"error": "Missing required fields"}), 400

        avatar_bytes = requests.get(avatar_url).content

        img = create_license_image(
            username, avatar_bytes, role, age, address,
            eye, height, datetime.utcnow(),
            datetime.utcnow(), license_id
        )

        # store in memory for lookup
        LICENSE_STORE[license_id] = {
            "username": username,
            "roleplay_name": role,
            "age": age,
            "address": address,
            "eye_color": eye,
            "height": height,
            "issued": str(datetime.utcnow().date()),
            "expires": str(datetime.utcnow().date()),
            "image": img
        }

        bot.loop.create_task(
            send_license_to_discord(img, f"{username}_license.png", discord_id)
        )

        return jsonify({"status": "ok", "license_id": license_id}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ======================================================
#  LOOKUP PAGE
# ======================================================

LOOKUP_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>License Lookup</title>
<style>
body {
    background:#f2f2f2;
    font-family:Arial, sans-serif;
    text-align:center;
}
.card {
    background:white;
    padding:25px;
    margin:20px auto;
    width:880px;
    border-radius:15px;
    box-shadow:0 0 15px rgba(0,0,0,0.15);
}
img {
    border-radius:10px;
    width:820px;
}
.info {
    text-align:left;
    margin-top:25px;
    padding:10px 20px;
}
button {
    margin-top:20px;
    padding:12px 25px;
    background:#2d6cdf;
    color:white;
    border:none;
    border-radius:8px;
    font-size:17px;
}
</style>
</head>
<body>

<div class="card">
    <h2>Driver License Lookup</h2>
    <img src="/license_image/{{lid}}" alt="License Image">

    <div class="info">
        <p><b>Name:</b> {{d.roleplay_name or d.username}}</p>
        <p><b>Age:</b> {{d.age}}</p>
        <p><b>Address:</b> {{d.address}}</p>
        <p><b>Eye Color:</b> {{d.eye_color}}</p>
        <p><b>Height:</b> {{d.height}}</p>
        <p><b>Issued:</b> {{d.issued}}</p>
        <p><b>Expires:</b> {{d.expires}}</p>
    </div>

    <a href="/license_image/{{lid}}" download="license_{{lid}}.png">
        <button>Download License Image</button>
    </a>
</div>

</body>
</html>
"""


@app.route("/lookup/<license_id>")
def lookup_page(license_id):
    if license_id not in LICENSE_STORE:
        return "License not found.", 404

    data = LICENSE_STORE[license_id]
    return render_template_string(LOOKUP_HTML, d=data, lid=license_id)


@app.route("/license_image/<license_id>")
def license_image(license_id):
    if license_id not in LICENSE_STORE:
        return "Not found", 404

    img_bytes = LICENSE_STORE[license_id]["image"]
    return send_file(io.BytesIO(img_bytes),
                     mimetype="image/png",
                     as_attachment=False,
                     download_name=f"{license_id}.png")


# ======================================================
#  BATCH GENERATOR
# ======================================================

@app.route("/license_batch", methods=["POST"])
def license_batch():
    try:
        data = request.json or {}
        batch = data.get("licenses", [])

        for entry in batch:
            try:
                avatar_bytes = requests.get(entry["roblox_avatar"]).content

                img = create_license_image(
                    entry["roblox_username"],
                    avatar_bytes,
                    entry.get("roleplay_name"),
                    entry.get("age"),
                    entry.get("address"),
                    entry.get("eye_color"),
                    entry.get("height"),
                    datetime.utcnow(),
                    datetime.utcnow(),
                    entry.get("license_id") or entry["roblox_username"]
                )

                LICENSE_STORE[entry.get("license_id") or entry["roblox_username"]] = {
                    "username": entry["roblox_username"],
                    "roleplay_name": entry.get("roleplay_name"),
                    "age": entry.get("age"),
                    "address": entry.get("address"),
                    "eye_color": entry.get("eye_color"),
                    "height": entry.get("height"),
                    "issued": str(datetime.utcnow().date()),
                    "expires": str(datetime.utcnow().date()),
                    "image": img
                }

                bot.loop.create_task(
                    send_license_to_discord(
                        img,
                        f"{entry['roblox_username']}_license.png",
                        entry.get("discord_id")
                    )
                )
            except Exception as e:
                print("[Batch Error]", e)

        return jsonify({"status": "ok", "processed": len(batch)})

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500


# ======================================================
#  BOT READY
# ======================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency * 1000)}ms`ms`")


# ======================================================
#  RUN
# ======================================================

def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    print("🚀 Flask API running...")
    app.run(host="0.0.0.0", port=8080)
