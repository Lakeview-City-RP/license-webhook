from __future__ import annotations

# --- stdlib
import os, io, json
from datetime import datetime
from threading import Thread

# --- third-party
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# --- discord.py
import discord
from discord.ext import commands

# ========= TOKEN & CONFIG =========
TOKEN = os.getenv("DISCORD_TOKEN")

# Optional local fallback
if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found! Set DISCORD_TOKEN or create token.txt")

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


# ---------- FONT LOADER ----------
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Best-effort load of a clean sans-serif font."""
    candidates = []
    if bold:
        candidates += ["arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    else:
        candidates += ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    return ImageFont.load_default()


# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, roleplay_name, age, address,
                         eye_color, height, issued, expires, lic_num):
    """Creates an ERLC-style Lakeview City Driver's License (compact card)."""

    W, H = 820, 520
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    card_bg = (250, 250, 252, 255)
    grey_dark = (40, 40, 40, 255)
    grey_mid = (75, 75, 75, 255)
    blue_accent = (50, 110, 200, 255)
    grid_color = (225, 230, 240, 80)
    dmv_gold = (220, 180, 80, 230)

    # Fonts
    title_font = load_font(42, bold=True)
    label_font = load_font(22, bold=True)
    value_font = load_font(22, bold=False)
    small_font = load_font(16, bold=False)

    # Rounded card background
    draw.rounded_rectangle((0, 0, W, H), radius=34, fill=card_bg)

    # Holographic-ish gradient background (drawn BEFORE text)
    for y in range(H):
        col = (255, 235 - int(20 * y / H), 170, 30)  # warm, low alpha
        draw.line((0, y, W, y), fill=col)

    # License-themed grid pattern
    for yy in range(0, H, 40):
        for xx in range(0, W, 40):
            draw.rectangle((xx + 10, yy + 10, xx + 26, yy + 26), fill=grid_color)

    # Diagonal LAKEVIEW watermark
    wm_text = "LAKEVIEW"
    wm_font = load_font(120, bold=True)
    wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wm_layer)
    tw = wdraw.textlength(wm_text, font=wm_font)
    tmp = Image.new("RGBA", (int(tw) + 40, 160), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tmp)
    tdraw.text((20, 0), wm_text, font=wm_font, fill=(150, 150, 150, 65))
    tmp = tmp.rotate(33, expand=True, resample=Image.BICUBIC)
    tmp = tmp.filter(ImageFilter.GaussianBlur(1.3))
    wm_x = W // 2 - tmp.width // 2
    wm_y = H // 2 - tmp.height // 2
    wm_layer.paste(tmp, (wm_x, wm_y), tmp)
    img = Image.alpha_composite(img, wm_layer)
    draw = ImageDraw.Draw(img)  # refresh draw after compositing

    # ==== CONTENT (drawn AFTER background & watermark) ====

    # Header text
    header = "Lakeview City • Driver’s License"
    header_w = draw.textlength(header, font=title_font)
    draw.text(((W - header_w) / 2, 20), header, fill=grey_dark, font=title_font)

    # Avatar (left)
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((200, 200))
            amask = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(amask).rounded_rectangle((0, 0, 200, 200), radius=26, fill=255)
            avatar.putalpha(amask)
            img.paste(avatar, (45, 130), avatar)
        except Exception as e:
            print("[Avatar Error]", e)

    # Left column: username + identity
    left_x = 280
    y = 130
    line_gap = 36

    # @username
    draw.text((left_x, y), f"@{username}", fill=blue_accent, font=label_font)
    y += line_gap

    def draw_label_value(x, y, label, value):
        draw.text((x, y), label, fill=grey_dark, font=label_font)
        lw = draw.textlength(label, font=label_font)
        draw.text((x + lw + 8, y), value or "N/A", fill=grey_mid, font=value_font)

    # Name
    draw_label_value(left_x, y, "Name:", roleplay_name or username)
    y += line_gap

    # Age
    draw_label_value(left_x, y, "Age:", age)
    y += line_gap

    # Address
    draw_label_value(left_x, y, "Address:", address)

    # Right column: physical info
    right_x = 280
    ry = 300
    draw_label_value(right_x, ry, "Eye Color:", eye_color)
    ry += line_gap
    draw_label_value(right_x, ry, "Height:", height)

    # DMV info divider line
    info_y = 380
    draw.line((40, info_y, W - 40, info_y), fill=(180, 180, 180, 255), width=2)

    # DMV info row
    info_y += 18
    draw.text((50, info_y), f"License: {lic_num}", fill=grey_dark, font=label_font)
    draw.text((330, info_y), f"Issued: {issued.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)
    draw.text((570, info_y), f"Expires: {expires.strftime('%Y-%m-%d')}", fill=grey_dark, font=label_font)

    # DMV notes
    notes_y = 440
    draw.text((50, notes_y), "This license is property of the Lakeview City DMV.", font=small_font, fill=grey_mid)
    draw.text((50, notes_y + 22), "Tampering, duplication, or misuse is prohibited by law.", font=small_font, fill=grey_mid)

    # DMV gold seal on the right
    seal = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(seal)
    sdraw.ellipse((0, 0, 160, 160), outline=(dmv_gold[0], dmv_gold[1], dmv_gold[2], 255), width=5)
    sdraw.ellipse((20, 20, 140, 140), outline=(dmv_gold[0], dmv_gold[1], dmv_gold[2], 160), width=2)
    sdraw.text((45, 60), "Lakeview\nCity DMV\nCertified", fill=dmv_gold, font=small_font, align="center")
    seal = seal.filter(ImageFilter.GaussianBlur(0.8))
    img.paste(seal, (W - 200, 170), seal)

    # Convert to PNG bytes
    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out.read()


# ---------- FLASK APP ----------
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
            return jsonify({"status": "error", "message": "Invalid avatar URL or username"}), 400

        avatar_bytes = requests.get(avatar_url, timeout=10).content

        img_data = create_license_image(
            username, avatar_bytes, roleplay_name, age, address,
            eye_color, height, datetime.utcnow(), datetime.utcnow(), "AUTO"
        )
        filename = f"{username}_license.png"

        async def send_license():
            await bot.wait_until_ready()

            channel = bot.get_channel(1436890841703645285)
            if channel:
                embed = discord.Embed(
                    title="Lakeview City Roleplay Driver’s License",
                    color=0x757575
                )
                embed.set_image(url=f"attachment://{filename}")
                await channel.send(
                    content=f"<@{discord_id}> Your license has been issued ✅",
                    embed=embed,
                    file=new_file(img_data, filename)
                )

            if discord_id:
                try:
                    user = await bot.fetch_user(int(discord_id))
                    if user:
                        dm_embed = discord.Embed(
                            title="Lakeview City Roleplay Driver’s License",
                            color=0x757575
                        )
                        dm_embed.set_image(url=f"attachment://{filename}")
                        await user.send(
                            embed=dm_embed,
                            file=new_file(img_data, filename)
                        )
                except Exception as e:
                    print(f"[DM Error] {e}")

        bot.loop.create_task(send_license())
        return jsonify({"status": "ok", "message": "License created"}), 200

    except Exception as e:
        import traceback
        print("[Webhook Exception]", e)
        print(traceback.format_exc())
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
