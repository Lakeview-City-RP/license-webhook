from __future__ import annotations

import os, io, json, asyncio
from datetime import datetime
from threading import Thread

import aiohttp, requests
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

# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height, issued, expires, lic_num):
    """Creates a premium Lakeview City DMV Driver License"""
    W, H = 850, 520
    img = Image.new("RGB", (W, H), (242, 247, 255))
    draw = ImageDraw.Draw(img)

    header_color = (30, 65, 135)
    accent = (70, 110, 200)
    text_color = (25, 30, 45)

    # --- Fonts ---
    def load_font(size, bold=False):
        for name in (["segoeuib.ttf", "segoeui.ttf"] if bold else ["segoeui.ttf", "DejaVuSans.ttf", "arial.ttf"]):
            try:
                return ImageFont.truetype(name, size)
            except:
                continue
        return ImageFont.load_default()

    font_title = load_font(64, bold=True)
    font_bold = load_font(28, bold=True)
    font_small = load_font(19)
    font_text = load_font(24)

    # --- Base rounded background ---
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=40, fill=255)
    base = Image.new("RGB", (W, H), (255, 255, 255))
    img.paste(base, (0, 0), mask)

    # --- Subtle pattern ---
    pattern = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pattern)
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            pdraw.rectangle((x, y, x+20, y+20), fill=(230, 235, 250, 55))
    img = Image.alpha_composite(img.convert("RGBA"), pattern)

    # --- Gold shimmer "LAKEVIEW" watermark ---
    wm_text = "LAKEVIEW"
    wm_font = load_font(150, bold=True)
    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    gradient = Image.new("RGBA", (W, H))
    gdraw = ImageDraw.Draw(gradient)
    for i in range(H):
        color = (
            int(255 - 30 * (i / H)),  # red
            int(200 - 80 * (i / H)),  # green
            int(120 - 60 * (i / H)),  # blue
            100  # alpha
        )
        gdraw.line((0, i, W, i), fill=color)
    tw, th = wdraw.textsize(wm_text, font=wm_font)
    text_img = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
    tdraw = ImageDraw.Draw(text_img)
    tdraw.text((0, 0), wm_text, font=wm_font, fill=(255, 255, 255, 255))
    text_img = text_img.rotate(35, expand=1)
    gradient = gradient.crop((0, 0, text_img.width, text_img.height))
    text_img = Image.alpha_composite(text_img, gradient)
    text_img = text_img.filter(ImageFilter.GaussianBlur(2))
    watermark.paste(text_img, (int(W/2 - text_img.width/2), int(H/2 - text_img.height/2)), text_img)
    img = Image.alpha_composite(img, watermark)

    # --- Header bar ---
    draw.rounded_rectangle((0, 0, W, 100), radius=40, fill=header_color)
    title = "LAKEVIEW CITY DRIVER’S LICENSE"
    tw, th = draw.textsize(title, font=font_title)
    draw.text(((W - tw) / 2, 18), title, fill="white", font=font_title)

    # --- Banner ---
    draw.text((20, 110), "CITY OF LAKEVIEW OFFICIAL USE ONLY • " * 5, fill=(100, 120, 160), font=font_small)

    # --- Avatar ---
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((180, 180))
            amask = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(amask).rounded_rectangle((0, 0, 180, 180), radius=40, fill=255)
            avatar.putalpha(amask)
            img.paste(avatar, (50, 170), avatar)
            draw.rounded_rectangle((50, 170, 230, 350), radius=40, outline=(150, 160, 180), width=3)
        except Exception as e:
            print("[Avatar Error]", e)

    # --- Identity left ---
    xL, yL, spacing = 260, 160, 40
    draw.text((xL, yL), "IDENTITY", fill=accent, font=font_bold)
    draw.text((xL, yL+spacing), f"Name: {roleplay_name or username}", fill=text_color, font=font_bold)
    draw.text((xL, yL+spacing*2), f"Age: {age or 'N/A'}", fill=text_color, font=font_bold)
    draw.text((xL, yL+spacing*3), f"Address: {address or 'N/A'}", fill=text_color, font=font_bold)

    # --- Physical right ---
    xR, yR = 560, 160
    draw.text((xR, yR), "PHYSICAL INFO", fill=accent, font=font_bold)
    draw.text((xR, yR+spacing), f"Eye Color: {eye_color or 'N/A'}", fill=text_color, font=font_bold)
    draw.text((xR, yR+spacing*2), f"Height: {height or 'N/A'}", fill=text_color, font=font_bold)

    # --- DMV Notes ---
    notes_top = 370
    draw.rounded_rectangle((30, notes_top, W-30, H-20), radius=25, outline=(160, 170, 190), width=2, fill=(235, 238, 250))
    draw.text((50, notes_top+10), "DMV NOTES", fill=accent, font=font_bold)
    draw.text(
        (50, notes_top+50),
        f"Issued: {issued.strftime('%Y-%m-%d')}     Expires: {expires.strftime('%Y-%m-%d')}\n\n"
        "This license is property of the Lakeview City DMV.\n"
        "Tampering or misuse is punishable by law.\n"
        "Verify authenticity at: https://lakeviewdmv.gov",
        fill=(50, 50, 60),
        font=font_small
    )

    # --- Circular DMV Seal ---
    seal = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    sdraw.ellipse((0, 0, 150, 150), outline=(220, 180, 80, 180), width=5)
    sdraw.text((20, 60), "Lakeview City\nDMV Certified", font=font_small, fill=(220, 180, 80, 180), align="center")
    seal = seal.filter(ImageFilter.GaussianBlur(0.5))
    img.paste(seal, (W-180, H-180), seal)

    # --- Holographic overlay ---
    holo = Image.new("RGBA", img.size)
    hdraw = ImageDraw.Draw(holo)
    for i in range(H):
        color = (255, 220 - int(30*(i/H)), 120, int(45 + 25*(i/H)))
        hdraw.line((0, i, W, i), fill=color)
    holo = holo.filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, holo)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# ---------- FLASK ----------
app = Flask(__name__)

@app.route("/license", methods=["POST"])
def license_endpoint():
    try:
        data = request.json
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

        avatar_bytes = requests.get(avatar_url).content
        img_data = create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height,
                                        datetime.utcnow(), datetime.utcnow(), "AUTO")

        async def send_license():
            await bot.wait_until_ready()
            channel = bot.get_channel(1436890841703645285)
            if not channel:
                return
            file = discord.File(io.BytesIO(img_data), filename=f"{username}_license.png")
            embed = discord.Embed(title="Lakeview City Roleplay Driver’s License", color=0xEAB308)
            embed.set_image(url=f"attachment://{username}_license.png")
            await channel.send(embed=embed, file=file)
            if discord_id:
                try:
                    user = bot.get_user(int(discord_id))
                    if user:
                        dm_embed = discord.Embed(title="Lakeview City Roleplay Driver’s License", color=0xEAB308)
                        dm_embed.set_image(url=f"attachment://{username}_license.png")
                        await user.send(embed=dm_embed, file=file)
                except Exception as e:
                    print(f"[DM Error] {e}")

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[Webhook Exception] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- BASIC COMMANDS ----------
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
    print(f"✅ Logged in as {bot.user}")

# ---------- RUN ----------
def run_bot(): bot.run(TOKEN)
if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
