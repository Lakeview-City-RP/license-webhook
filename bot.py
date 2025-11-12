from __future__ import annotations

# --- stdlib
import os, io, json, asyncio
from datetime import datetime
from threading import Thread

# --- third-party
import aiohttp, requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py
import discord
from discord.ext import commands

# ========= TOKEN & CONFIG =========
TOKEN = os.getenv("DISCORD_TOKEN")

# ✅ Optional local fallback for testing
if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found! Set DISCORD_TOKEN in Render or create token.txt locally.")

GUILD_ID = int(os.getenv("GUILD_ID", "0"))
PREFIX = "?"
LICENSES_DIR = "licenses"
JSON_FILE = "licenses.json"

# ========= DISCORD SETUP =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

os.makedirs(LICENSES_DIR, exist_ok=True)
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)


# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, roleplay_name, age, address, eye_color, height, issued, expires, lic_num):
    """Creates a realistic Lakeview City DMV Driver License"""
    W, H = 850, 520
    img = Image.new("RGB", (W, H), (242, 247, 255))
    draw = ImageDraw.Draw(img)

    # --- Colors ---
    header_color = (30, 65, 135)
    accent = (70, 110, 200)
    text_color = (25, 30, 45)

    # --- Fonts ---
    def load_font(name: str, size: int):
        for path in ["segoeui.ttf", "segoeuib.ttf", "DejaVuSans.ttf", "arial.ttf"]:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        return ImageFont.load_default()

    font_title = load_font("segoeuib.ttf", 64)
    font_bold = load_font("segoeuib.ttf", 28)
    font_text = load_font("segoeui.ttf", 24)
    font_small = load_font("segoeui.ttf", 19)

    # --- Rounded base ---
    base = Image.new("RGB", (W, H), (255, 255, 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), radius=40, fill=255)
    img.paste(base, (0, 0), mask)

    # --- Subtle pattern background ---
    pattern = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pattern)
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            pdraw.rectangle((x, y, x + 20, y + 20), fill=(230, 235, 250, 55))
    img = Image.alpha_composite(img.convert("RGBA"), pattern)

    # --- Large diagonal watermark (LAKEVIEW) ---
    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    wm_text = "LAKEVIEW"
    wm_font = load_font("segoeuib.ttf", 150)
    tw, th = wdraw.textsize(wm_text, font=wm_font)
    txt_layer = Image.new("RGBA", (tw + 20, th + 20), (255, 255, 255, 0))
    tdraw = ImageDraw.Draw(txt_layer)
    tdraw.text((10, 0), wm_text, fill=(200, 200, 200, 50), font=wm_font)
    txt_layer = txt_layer.rotate(35, expand=1)
    watermark.paste(txt_layer, (int(W / 2 - txt_layer.width / 2), int(H / 2 - txt_layer.height / 2)), txt_layer)
    img = Image.alpha_composite(img, watermark)

    # --- Header Title ---
    draw.rounded_rectangle((0, 0, W, 100), radius=40, fill=header_color)
    title_text = "LAKEVIEW CITY DRIVER’S LICENSE"
    tw, th = draw.textsize(title_text, font=font_title)
    draw.text(((W - tw) / 2, 18), title_text, fill="white", font=font_title)

    # --- Banner ---
    banner_y = 110
    banner_text = "CITY OF LAKEVIEW OFFICIAL USE ONLY • " * 5
    draw.text((20, banner_y), banner_text, fill=(100, 120, 160), font=font_small)

    # --- Avatar ---
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((180, 180))
            amask = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(amask).rounded_rectangle((0, 0, 180, 180), radius=40, fill=255)
            avatar.putalpha(amask)
            img.paste(avatar, (50, 170), avatar)
            draw.rounded_rectangle((50, 170, 230, 350), radius=40, outline=(150, 160, 180), width=3)
        except Exception as e:
            print("[Avatar Error]", e)

    # --- Identity (left) ---
    xL = 260
    y = 160
    spacing = 40
    draw.text((xL, y), "IDENTITY", fill=accent, font=font_bold)
    y += spacing
    draw.text((xL, y), f"Name: {roleplay_name or username}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((xL, y), f"Age: {age or 'N/A'}", fill=text_color, font=font_bold)
    y += spacing
    draw.text((xL, y), f"Address: {address or 'N/A'}", fill=text_color, font=font_bold)

    # --- Physical Info (right) ---
    xR = 560
    yR = 160
    draw.text((xR, yR), "PHYSICAL INFO", fill=accent, font=font_bold)
    yR += spacing
    draw.text((xR, yR), f"Eye Color: {eye_color or 'N/A'}", fill=text_color, font=font_bold)
    yR += spacing
    draw.text((xR, yR), f"Height: {height or 'N/A'}", fill=text_color, font=font_bold)

    # --- DMV Notes ---
    notes_top = 370
    draw.rounded_rectangle((30, notes_top, W - 30, H - 20), radius=25, outline=(160, 170, 190), width=2, fill=(235, 238, 250))
    draw.text((50, notes_top + 10), "DMV NOTES", fill=accent, font=font_bold)
    draw.text(
        (50, notes_top + 50),
        f"Issued: {issued.strftime('%Y-%m-%d')}     Expires: {expires.strftime('%Y-%m-%d')}\n\n"
        "This license is property of the Lakeview City DMV.\n"
        "Tampering, duplication, or misuse is prohibited by law.\n"
        "Verify authenticity at: https://lakeviewdmv.gov",
        fill=(50, 50, 60),
        font=font_small,
    )

    # --- Holographic overlay ---
    holo = Image.new("RGBA", img.size)
    hdraw = ImageDraw.Draw(holo)
    for i in range(H):
        color = (180 + int(40 * (i / H)), 200 + int(30 * (1 - i / H)), 255, int(45 + 25 * (i / H)))
        hdraw.line((0, i, W, i), fill=color)
    holo = holo.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, holo)

    # Output
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out.read()


# ---------- FLASK APP ----------
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
            return jsonify({"status": "error", "message": "Invalid avatar URL or username"}), 400

        avatar_bytes = requests.get(avatar_url).content
        img_data = create_license_image(
            username, avatar_bytes, roleplay_name, age, address, eye_color, height,
            datetime.utcnow(), datetime.utcnow(), "AUTO"
        )

        async def send_license():
            await bot.wait_until_ready()
            channel = bot.get_channel(1436890841703645285)
            if not channel:
                print("[Webhook Error] License channel not found")
                return

            file = discord.File(io.BytesIO(img_data), filename=f"{username}_license.png")

            # Channel embed
            embed = discord.Embed(
                title="Lakeview City Roleplay Driver’s License",
                color=0x4A90E2
            )
            embed.set_image(url=f"attachment://{username}_license.png")
            await channel.send(embed=embed, file=file)

            # DM embed
            if discord_id:
                try:
                    user = bot.get_user(int(discord_id))
                    if user:
                        dm_embed = discord.Embed(
                            title="Lakeview City Roleplay Driver’s License",
                            color=0x4A90E2
                        )
                        dm_embed.set_image(url=f"attachment://{username}_license.png")
                        await user.send(embed=dm_embed, file=file)
                except Exception as e:
                    print(f"[DM Error] {e}")

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok", "message": "License created"}), 200

    except Exception as e:
        print(f"[Webhook Exception] {type(e).__name__}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------- BASIC COMMAND ----------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! 🏓 `{round(bot.latency * 1000)}ms`")


@bot.command()
async def license(ctx):
    await ctx.send("✅ License system online and ready.")
    try:
        await ctx.message.delete()
    except:
        pass


# ---------- BOT READY ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")


# ---------- RUN ----------
def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🚀 Starting Flask server for Render...")
    app.run(host="0.0.0.0", port=8080)
