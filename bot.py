from __future__ import annotations

# --- stdlib ---
import os
import io
import math
import asyncio
import json
import time
from datetime import datetime, timedelta
from threading import Thread

print("BOT PID:", os.getpid())
import aiosqlite
import sqlite3  # Needed for the synchronous part in Flask

# --- third-party ---
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# --- discord.py ---
import discord
from discord.ext import commands

# ============================================================
# CONSTANTS (IDS)
# ============================================================

LOG_CHANNEL_ID = 1436890841703645285

ROLE_PROV_1_ID = 1436150194726113330
ROLE_PROV_2_ID = 1454680487917256786
ROLE_OFFICIAL_ID = 1455075670907686912

DB_PATH = "workforce.db"

# ============================================================
# GOOGLE SHEETS CONFIG
# ============================================================

SHEET_NAME = "Registered Licenses: LKVCWL"
WORKSHEET_NAME = "Licenses"

# Either provide a file path OR a full JSON string via env var.
# DO NOT COMMIT THESE FILES.
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")  # optional

# ============================================================
# TOKEN / DISCORD SETUP
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    print("⚠️  Warning: Discord token not found in env or token.txt")

PREFIX = "?"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)


# ============================================================
# GOOGLE SHEETS HELPER
# ============================================================

def _get_gspread_client() -> gspread.Client:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if SERVICE_ACCOUNT_JSON:
        info = json.loads(SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    return gspread.authorize(creds)


def _ensure_header(ws: gspread.Worksheet):
    """
    Ensures the sheet has a header row. If empty, creates a default header.
    """
    header = ws.row_values(1)
    if header:
        return

    ws.append_row([
        "Discord ID",
        "Roblox Username",
        "Roblox Display",
        "Roleplay Name",
        "License Number",
        "License Type",
        "License Code",
        "Issued (UTC)",
        "Expires (UTC)",
        "Last Updated (UTC)"
    ])


def upsert_license_to_sheet(license_info: dict):
    """
    Upserts a license row into:
      Spreadsheet name: Registered Licenses: LKVCWL
      Worksheet: Licenses

    Matching key: Discord ID (column A)
    If not found -> append row.
    If found -> update row.
    """
    # Best-effort retries (network hiccups)
    for attempt in range(1, 4):
        try:
            gc = _get_gspread_client()
            sh = gc.open(SHEET_NAME)
            ws = sh.worksheet(WORKSHEET_NAME)

            _ensure_header(ws)

            discord_id = str(license_info.get("discord_id", "")).strip()
            if not discord_id:
                raise ValueError("license_info.discord_id missing")

            now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # Build row in the same order as header
            row = [
                discord_id,
                str(license_info.get("roblox_username", "") or ""),
                str(license_info.get("roblox_display", "") or ""),
                str(license_info.get("roleplay_name", "") or ""),
                str(license_info.get("license_number", "") or ""),
                str(license_info.get("license_type", "") or ""),
                str(license_info.get("license_code", "") or ""),
                str(license_info.get("issued_at", "") or ""),
                str(license_info.get("expires_at", "") or ""),
                now_utc,
            ]

            # Find discord_id in column A (skip header)
            col_a = ws.col_values(1)  # includes header row
            target_row_idx = None
            for idx, val in enumerate(col_a[1:], start=2):
                if str(val).strip() == discord_id:
                    target_row_idx = idx
                    break

            if target_row_idx is None:
                ws.append_row(row, value_input_option="USER_ENTERED")
            else:
                # Update A..J on that row
                ws.update(f"A{target_row_idx}:J{target_row_idx}", [row], value_input_option="USER_ENTERED")

            return  # success

        except Exception as e:
            print(f"[Sheets] attempt {attempt} failed: {e}")
            if attempt == 3:
                return
            time.sleep(1.5 * attempt)


def schedule_sheet_upsert(license_info: dict):
    """
    Runs Sheets update in a background thread so the Flask request returns fast.
    """
    Thread(target=upsert_license_to_sheet, args=(license_info,), daemon=True).start()


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
        license_type
):
    W, H = 820, 520

    username_str = str(username or "")
    roleplay_name_str = str(roleplay_name or username_str)
    age_str = str(age or "")
    addr_str = str(address or "")
    eye_str = str(eye_color or "")
    height_str = str(height or "")
    lic_num_str = str(lic_num or "")

    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(full_mask).rounded_rectangle((0, 0, W, H), 120, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    base.putalpha(full_mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)

    for y in range(H):
        ratio = y / H

        if license_type == "provisional":
            r = int(255 - 50 * ratio)
            g = int(150 + 40 * ratio)
            b = int(60 - 40 * ratio)
        else:
            r = int(150 + 40 * ratio)
            g = int(180 + 50 * ratio)
            b = int(220 + 20 * ratio)

        r = min(255, max(0, r))
        g = min(255, max(0, g))
        b = min(255, max(0, b))

        bgd.line((0, y, W, y), fill=(r, g, b))

    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)

    mesh_color = (255, 180, 100, 45) if license_type == "provisional" else (255, 255, 255, 40)

    for x in range(0, W, 40):
        for y in range(0, H, 40):
            wd.arc((x, y, x + 80, y + 80), 0, 180, fill=mesh_color, width=2)

    wave = wave.filter(ImageFilter.GaussianBlur(1.2))
    bg.alpha_composite(wave)

    bg.putalpha(full_mask)
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    HEADER_H = 95

    if license_type == "provisional":
        header_color_start = (225, 140, 20)
        header_color_end = (255, 200, 80)
        title_text = "LAKEVIEW PROVISIONAL LICENSE"
        title_font = load_font(35, bold=True)
    else:
        header_color_start = (35, 70, 160)
        header_color_end = (60, 100, 190)
        title_text = "LAKEVIEW CITY DRIVER LICENSE"
        title_font = load_font(39, bold=True)

    header = Image.new("RGBA", (W, HEADER_H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)

    for i in range(HEADER_H):
        t = i / HEADER_H
        r = int(header_color_start[0] + (header_color_end[0] - header_color_start[0]) * t)
        g = int(header_color_start[1] + (header_color_end[1] - header_color_start[1]) * t)
        b = int(header_color_start[2] + (header_color_end[2] - header_color_start[2]) * t)
        hd.line((0, i, W, i), fill=(r, g, b))

    header.putalpha(full_mask.crop((0, 0, W, HEADER_H)))
    card.alpha_composite(header, (0, 0))

    tw = draw.textlength(title_text, font=title_font)
    draw.text((W / 2 - tw / 2 + 2, 26 + 2), title_text, fill=(0, 0, 0, 120), font=title_font)
    draw.text((W / 2 - tw / 2, 26), title_text, fill="white", font=title_font)

    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((200, 200))
        m = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, 200, 200), 42, fill=255)
        av.putalpha(m)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58, 158))
        card.alpha_composite(av, (50, 150))
    except:
        pass

    section = load_font(24, bold=True)
    boldf = load_font(22, bold=True)
    normal = load_font(22)

    blue = (160, 70, 20) if license_type == "provisional" else (50, 110, 200)
    grey = (35, 35, 35)

    def ot(x, y, txt, font, fill):
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + ox, y + oy), txt, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), txt, font=font, fill=fill)

    ix, iy = 290, 160
    ot(ix, iy, "IDENTITY:", section, blue)
    draw.line((ix, iy + 34, ix + 250, iy + 34), fill=blue, width=3)

    iy += 55

    def wp(x, y, label, value):
        lw = draw.textlength(label, font=boldf)
        draw.text((x, y), label, font=boldf, fill=grey)
        draw.text((x + lw + 10, y), value, font=normal, fill=grey)

    wp(ix, iy, "Name:", roleplay_name_str)
    wp(ix, iy + 34, "Age:", age_str)
    wp(ix, iy + 68, "Address:", addr_str)

    px, py = 550, 160
    ot(px, py, "PHYSICAL:", section, blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)

    py += 55
    wp(px, py, "Eye Color:", eye_str)
    wp(px, py + 34, "Height:", height_str)

    BOX_Y, BOX_H = 360, 140

    if license_type == "provisional":
        fill_color = (255, 190, 130, 130)
        outline_color = (180, 90, 20, 255)
    else:
        fill_color = (200, 220, 255, 90)
        outline_color = (80, 140, 255, 180)

    box = Image.new("RGBA", (W - 80, BOX_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)

    bd.rounded_rectangle((0, 0, W - 80, BOX_H), radius=45, fill=fill_color, outline=outline_color, width=3)
    card.alpha_composite(box, (40, BOX_Y))

    ot(60, BOX_Y + 15, "DMV INFO:", section, blue)
    draw.line((60, BOX_Y + 47, 300, BOX_Y + 47), fill=blue, width=3)

    y2 = BOX_Y + 65
    draw.text((60, y2), "License Class:", font=boldf, fill=grey)
    draw.text((245, y2), "Provisional" if license_type == "provisional" else "Standard", font=normal, fill=grey)

    draw.text((430, y2), f"License #: {lic_num_str}", font=normal, fill=grey)

    y2 += 38
    draw.text((60, y2), "Issued:", font=boldf, fill=grey)
    draw.text((150, y2), issued.strftime("%Y-%m-%d"), font=normal, fill=grey)

    draw.text((330, y2), "Expires:", font=boldf, fill=grey)
    draw.text((430, y2), expires.strftime("%Y-%m-%d"), font=normal, fill=grey)

    seal = Image.new("RGBA", (95, 95), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal)

    cx, cy = 48, 48
    R1, R2 = 44, 19
    pts = []

    for i in range(16):
        ang = math.radians(i * 22.5)
        r = R1 if i % 2 == 0 else R2
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

    if license_type == "provisional":
        seal_color = (255, 150, 40)
        outline_c = (255, 230, 180)
    else:
        seal_color = (40, 90, 180)
        outline_c = (255, 255, 255)

    sd.polygon(pts, fill=seal_color, outline=outline_c, width=3)
    seal = seal.filter(ImageFilter.GaussianBlur(1.0))

    card.alpha_composite(seal, (W - 150, BOX_Y + 10))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ============================================================
# DB MIGRATION HELPERS
# ============================================================

def _ensure_license_table_and_columns(conn: sqlite3.Connection):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            discord_id TEXT PRIMARY KEY,
            roblox_username TEXT,
            roblox_display TEXT,
            roleplay_name TEXT,
            age TEXT,
            address TEXT,
            eye_color TEXT,
            height TEXT,
            license_number TEXT,
            issued_at TEXT,
            expires_at TEXT
        )
    """)
    conn.commit()

    cur.execute("PRAGMA table_info(licenses)")
    cols = {row[1] for row in cur.fetchall()}

    if "license_type" not in cols:
        cur.execute("ALTER TABLE licenses ADD COLUMN license_type TEXT")
    if "license_code" not in cols:
        cur.execute("ALTER TABLE licenses ADD COLUMN license_code TEXT")

    conn.commit()


# ============================================================
# SEND TO DISCORD (DM + ROLES + LOG)
# ============================================================

async def send_license_to_discord(img_data, filename, discord_id, license_type="official"):
    await bot.wait_until_ready()

    license_type = (license_type or "official").lower().strip()
    if license_type in ("standard", "full", "official"):
        normalized_type = "official"
    elif license_type == "provisional":
        normalized_type = "provisional"
    else:
        normalized_type = "official"

    file_dm = discord.File(io.BytesIO(img_data), filename=filename)
    file_ch = discord.File(io.BytesIO(img_data), filename=filename)

    dm_success = False

    # 1) DM the user (ping them)
    try:
        user = await bot.fetch_user(int(discord_id))
        if user:
            if normalized_type == "provisional":
                dm_content = (
                    f"<@{discord_id}>\n"
                    "✅ Your **Provisional License** has been generated. The license image is attached below."
                )
                embed_dm = discord.Embed(
                    title="🔰 Provisional License Issued",
                    description="Please follow all learner / provisional restrictions while driving.",
                    color=0xE67E22
                )
            else:
                dm_content = (
                    f"<@{discord_id}>\n"
                    "✅ Your **Official License** has been generated. The license image is attached below."
                )
                embed_dm = discord.Embed(
                    title="🪪 Official Lakeview City License",
                    description="Your provisional status has been upgraded to an official license (where applicable).",
                    color=0x2ECC71
                )

            embed_dm.set_image(url=f"attachment://{filename}")
            embed_dm.set_footer(
                text="Lakeview City DMV • Official Document",
                icon_url=bot.user.avatar.url if bot.user.avatar else None
            )

            await user.send(content=dm_content, embed=embed_dm, file=file_dm)
            dm_success = True
    except Exception as e:
        print(f"Failed to DM user: {e}")

    # 2) Channel + roles
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except:
            channel = None

    guild = None
    if channel and hasattr(channel, "guild"):
        guild = channel.guild
    elif bot.guilds:
        guild = bot.guilds[0]

    try:
        if guild:
            member = guild.get_member(int(discord_id))
            if not member:
                try:
                    member = await guild.fetch_member(int(discord_id))
                except:
                    member = None

            if member:
                ROLE_PROV_1 = guild.get_role(ROLE_PROV_1_ID)
                ROLE_PROV_2 = guild.get_role(ROLE_PROV_2_ID)
                ROLE_OFFICIAL = guild.get_role(ROLE_OFFICIAL_ID)

                if normalized_type == "provisional":
                    if ROLE_PROV_1:
                        await member.add_roles(ROLE_PROV_1, reason="Provisional license generated")
                    if ROLE_PROV_2:
                        await member.add_roles(ROLE_PROV_2, reason="Provisional license generated")
                else:
                    if ROLE_PROV_2:
                        await member.remove_roles(ROLE_PROV_2, reason="Upgraded to official license")
                    if ROLE_OFFICIAL:
                        await member.add_roles(ROLE_OFFICIAL, reason="Official license generated")
    except Exception as e:
        print(f"Role management error: {e}")

    if channel:
        status = "Check your DMs!" if dm_success else "Your DMs are closed, so I'm posting it here!"
        embed_ch = discord.Embed(
            description=f"**License Issued for <@{discord_id}>**\n{status}",
            color=0x3498db
        )
        embed_ch.set_image(url=f"attachment://{filename}")
        embed_ch.set_footer(text="DMV Registry System")
        await channel.send(content=f"<@{discord_id}>", embed=embed_ch, file=file_ch)


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

        incoming_type = (data.get("license_type", "official") or "official").lower().strip()
        if incoming_type in ("standard", "official", "full"):
            license_type = "official"
        elif incoming_type == "provisional":
            license_type = "provisional"
        else:
            license_type = "official"

        license_code = data.get("license_code", "C")
        lic_num = data.get("license_number", username)

        if not username or not avatar or not discord_id:
            return jsonify({"status": "error", "message": "Missing username/avatar/discord_id"}), 400

        avatar_bytes = requests.get(avatar).content

        issued = datetime.utcnow()
        expires = issued + (timedelta(days=3) if license_type == "provisional" else timedelta(days=150))

        img = create_license_image(
            username, avatar_bytes, display, roleplay, age, addr, eye, height,
            issued, expires, lic_num, license_type
        )

        # Discord post/DM/roles
        bot.loop.create_task(
            send_license_to_discord(img, f"{username}_license.png", discord_id, license_type)
        )

        # Save to DB
        conn = sqlite3.connect(DB_PATH)
        _ensure_license_table_and_columns(conn)
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO licenses (
                discord_id,
                roblox_username,
                roblox_display,
                roleplay_name,
                age,
                address,
                eye_color,
                height,
                license_number,
                issued_at,
                expires_at,
                license_type,
                license_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                roblox_username = excluded.roblox_username,
                roblox_display  = excluded.roblox_display,
                roleplay_name   = excluded.roleplay_name,
                age             = excluded.age,
                address         = excluded.address,
                eye_color       = excluded.eye_color,
                height          = excluded.height,
                license_number  = excluded.license_number,
                issued_at       = excluded.issued_at,
                expires_at      = excluded.expires_at,
                license_type    = excluded.license_type,
                license_code    = excluded.license_code
            """,
            (
                str(discord_id),
                username,
                display,
                roleplay,
                age,
                addr,
                eye,
                height,
                lic_num,
                issued.isoformat(),
                expires.isoformat(),
                license_type,
                license_code,
            ),
        )

        conn.commit()
        conn.close()

        # Google Sheets upsert (append if not found)
        license_info = {
            "discord_id": str(discord_id),
            "roblox_username": username,
            "roblox_display": display,
            "roleplay_name": roleplay,
            "license_number": lic_num,
            "license_type": license_type,
            "license_code": license_code,
            "issued_at": issued.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"),
        }
        schedule_sheet_upsert(license_info)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# SINGLE CORRECT SETUP HOOK
# ============================================================

async def setup_hook():
    bot.db = await aiosqlite.connect(DB_PATH)

    extensions = [

    ]

    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Loaded {ext}")
        except Exception as e:
            print(f"Skipped {ext}: {e}")


bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    if getattr(bot, "did_ready", False):
        return
    bot.did_ready = True

    print(f"✅ Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced: {len(synced)}")
    except Exception as e:
        print(f"Sync error: {e}")


# ============================================================
# RUN BOT + FLASK (ONLY ONCE)
# ============================================================

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(TOKEN)
