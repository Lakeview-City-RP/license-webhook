from __future__ import annotations

import os, io, json, asyncio
from datetime import datetime
from threading import Thread
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify
import discord
from discord.ext import commands

# ========= TOKEN & CONFIG =========
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

# ---------- FONT LOADER ----------
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if bold:
        candidates += [
            os.path.join(here, "segoeuib.ttf"),
            os.path.join(here, "DejaVuSans-Bold.ttf"),
            "arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates += [
            os.path.join(here, "segoeui.ttf"),
            os.path.join(here, "DejaVuSans.ttf"),
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height, issued, expires, lic_num):
    """Creates a refined Lakeview City DMV Driver License"""
    W, H = 850, 520
    img = Image.new("RGB", (W, H), (242, 247, 255))
    draw = ImageDraw.Draw(img)

    header_color = (30, 65, 135)
    accent = (70, 110, 200)
    text_color = (25, 30, 45)

    font_title = load_font(72, bold=True)
    font_bold = load_font(28, bold=True)
    font_text = load_font(24)
    font_small = load_font(17)

    # Rounded card base
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=40, fill=255)
    base = Image.new("RGB", (W, H), (255, 255, 255))
    img.paste(base, (0, 0), mask)

    # Pattern background
    pattern = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pattern)
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            pdraw.rectangle((x, y, x+20, y+20), fill=(230, 235, 250, 55))
    img = Image.alpha_composite(img.convert("RGBA"), pattern)

    # Matte watermark “LAKEVIEW”
    wm_text = "LAKEVIEW"
    wm_font = load_font(110, bold=True)
    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    tw, th = wdraw.textlength(wm_text, font=wm_font), wm_font.size + 20
    text_img = Image.new("RGBA", (int(tw)+20, int(th)+20), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_img)
    tdraw.text((10, 0), wm_text, font=wm_font, fill=(200, 200, 200, 40))
    text_img = text_img.rotate(35, expand=True, resample=Image.BICUBIC)
    watermark.paste(text_img, (int(W/2 - text_img.width/2), int(H/2 - text_img.height/2)), text_img)
    img = Image.alpha_composite(img, watermark)

    draw = ImageDraw.Draw(img)

    # Header
    draw.rounded_rectangle((0, 0, W, 100), radius=40, fill=header_color)
    title = "LAKEVIEW CITY"
    tw = draw.textlength(title, font=font_title)
    draw.text(((W - tw) / 2, 15), title, fill="white", font=font_title)

    # Centered banner
    banner = "CITY OF LAKEVIEW OFFICIAL USE ONLY"
    bw = draw.textlength(banner, font=font_small)
    draw.text(((W - bw) / 2, 110), banner, fill=(100, 120, 160), font=font_small)

    # Avatar + label
    if avatar_bytes:
        draw.text((50, 135), "DRIVER’S LICENSE:", fill=accent, font=font_bold)
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((180, 180))
            amask = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(amask).rounded_rectangle((0, 0, 180, 180), radius=40, fill=255)
            avatar.putalpha(amask)
            img.paste(avatar, (50, 170), avatar)
            draw.rounded_rectangle((50, 170, 230, 350), radius=40, outline=(150, 160, 180), width=3)
        except Exception as e:
            print("[Avatar Error]", e)

    # Identity
    xL, yL, spacing = 260, 160, 40
    draw.text((xL, yL), "IDENTITY", fill=accent, font=font_bold)
    draw.text((xL, yL+spacing),   f"Name: {roleplay_name or username}", fill=text_color, font=font_bold)
    draw.text((xL, yL+spacing*2), f"Age: {age or 'N/A'}", fill=text_color, font=font_bold)
    draw.text((xL, yL+spacing*3), f"Address: {address or 'N/A'}", fill=text_color, font=font_bold)

    # Physical info
    xR, yR = 560, 160
    draw.text((xR, yR), "PHYSICAL INFO", fill=accent, font=font_bold)
    draw.text((xR, yR+spacing),   f"Eye Color: {eye_color or 'N/A'}", fill=text_color, font=font_bold)
    draw.text((xR, yR+spacing*2), f"Height: {height or 'N/A'}", fill=text_color, font=font_bold)

    # DMV Notes
    notes_top = 370
    draw.rounded_rectangle((30, notes_top, W-30, H-25), radius=25, outline=(160, 170, 190), width=2, fill=(235, 238, 250))
    draw.text((50, notes_top+8), "DMV NOTES", fill=accent, font=font_bold)
    text = (
        f"Issued: {issued.strftime('%Y-%m-%d')}     Expires: {expires.strftime('%Y-%m-%d')}\n\n"
        "This license is property of the Lakeview City DMV.\n"
        "Tampering, duplication, or misuse is prohibited by law.\n"
        "Verify authenticity at: https://lakeviewdmv.gov"
    )
    draw.text((50, notes_top+45), text, fill=(50, 50, 60), font=font_small)

    # DMV Seal
    seal = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    sdraw.ellipse((0, 0, 150, 150), outline=(220, 180, 80, 180), width=5)
    sdraw.ellipse((15, 15, 135, 135), outline=(220, 180, 80, 120), width=2)
    sdraw.text((25, 60), "Lakeview City\nDMV Certified", font=font_small, fill=(220, 180, 80, 180), align="center")
    seal = seal.filter(ImageFilter.GaussianBlur(0.5))
    img.paste(seal, (W-180, H-220), seal)

    # Holographic overlay
    holo = Image.new("RGBA", img.size)
    hdraw = ImageDraw.Draw(holo)
    for i in range(H):
        color = (255, 220 - int(30*(i/H)), 120, int(40 + 25*(i/H)))
        hdraw.line((0, i, W, i), fill=color)
    holo = holo.filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, holo)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# ---------- FLASK ----------
app = Flask(__name__)

def new_file(img_bytes: bytes, filename: str) -> discord.File:
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

        if not username or not avatar_url or not avatar_url.startswith("http"):
            return jsonify({"status": "error", "message": "Invalid data"}), 400

        avatar_bytes = requests.get(avatar_url, timeout=15).content
        img_bytes = create_license_image(
            username, avatar_bytes, roleplay_name, age, address, eye_color, height,
            datetime.utcnow(), datetime.utcnow(), "AUTO"
        )
        filename = f"{username}_license.png"

        async def send_license():
            await bot.wait_until_ready()
            channel = bot.get_channel(1436890841703645285)
            if channel:
                embed = discord.Embed(title="Lakeview City Roleplay Driver’s License", color=0x757575)
                embed.set_image(url=f"attachment://{filename}")
                await channel.send(content=f"<@{discord_id}>, your license has been issued ✅", embed=embed, file=new_file(img_bytes, filename))

            if discord_id:
                try:
                    user = await bot.fetch_user(int(discord_id))
                    if user:
                        dm_embed = discord.Embed(title="Lakeview City Roleplay Driver’s License", color=0x757575)
                        dm_embed.set_image(url=f"attachment://{filename}")
                        await user.send(embed=dm_embed, file=new_file(img_bytes, filename))
                except Exception as e:
                    print(f"[DM Error] {e}")

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[Webhook Exception] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- COMMANDS ----------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency*1000)}ms`")

@bot.command()
async def license(ctx):
    await ctx.send("✅ License system online.")
    try:
        await ctx.message.delete()
    except:
        pass

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

# ---------- RUN ----------
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
