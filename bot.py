from __future__ import annotations

# --- stdlib ---
import os
import io
import math
import asyncio
from datetime import datetime, timedelta
from threading import Thread

print("BOT PID:", os.getpid())
import aiosqlite
import sqlite3  # Needed for the synchronous part in Flask

# --- third-party ---
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

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
# TOKEN / DISCORD SETUP
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    # Just a warning so it doesn't crash if you run it locally without env vars immediately
    print("⚠️  Warning: Discord token not found in env or token.txt")

PREFIX = "?"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
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
    # --- CANVAS SIZE ---
    W, H = 820, 520

    # --- SAFE STRINGS ---
    username_str = str(username or "")
    roleplay_name_str = str(roleplay_name or username_str)
    age_str = str(age or "")
    addr_str = str(address or "")
    eye_str = str(eye_color or "")
    height_str = str(height or "")
    lic_num_str = str(lic_num or "")

    # --- BASE CARD ---
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(full_mask).rounded_rectangle((0, 0, W, H), 120, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    base.putalpha(full_mask)
    card = base.copy()
    draw = ImageDraw.Draw(card)

    # ====================================================
    # BACKGROUND GRADIENT
    # ====================================================
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

    # ====================================================
    # MESH / WAVE PATTERN
    # ====================================================
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

    # ====================================================
    # HEADER BAR
    # ====================================================
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

    # Title shadow + text
    tw = draw.textlength(title_text, font=title_font)
    draw.text((W / 2 - tw / 2 + 2, 26 + 2), title_text, fill=(0, 0, 0, 120), font=title_font)
    draw.text((W / 2 - tw / 2, 26), title_text, fill="white", font=title_font)

    # ====================================================
    # AVATAR
    # ====================================================
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

    # ====================================================
    # TEXT COLORS & FONTS
    # ====================================================
    section = load_font(24, bold=True)
    boldf = load_font(22, bold=True)
    normal = load_font(22)

    blue = (160, 70, 20) if license_type == "provisional" else (50, 110, 200)
    grey = (35, 35, 35)

    # outline text helper
    def ot(x, y, txt, font, fill):
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + ox, y + oy), txt, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), txt, font=font, fill=fill)

    # ====================================================
    # IDENTITY SECTION
    # ====================================================
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

    # ====================================================
    # PHYSICAL SECTION
    # ====================================================
    px, py = 550, 160
    ot(px, py, "PHYSICAL:", section, blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)

    py += 55
    wp(px, py, "Eye Color:", eye_str)
    wp(px, py + 34, "Height:", height_str)

    # ====================================================
    # DMV INFO BOX
    # ====================================================
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

    # DMV text
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

    # ====================================================
    # STAR SEAL
    # ====================================================
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

    # ====================================================
    # EXPORT BUFFER
    # ====================================================
    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ============================================================
# SHEETS SYNC (ROBUST: SYNC OR ASYNC)
# ============================================================

def _schedule_sheet_update(discord_id: str, license_info: dict, points: int = 0):
    """
    Safe to call from Flask thread. Schedules DMV Cog sheet update in the bot loop.
    Works whether _update_google_sheet_row is sync or async.
    """
    try:
        dmv = bot.get_cog("DMVCog")
        if not dmv or not hasattr(dmv, "_update_google_sheet_row"):
            return

        class FakeMember:
            def __init__(self, did):
                self.id = int(did)

            def __str__(self):
                return f"{self.id}"

        member = FakeMember(discord_id)

        fn = dmv._update_google_sheet_row

        if asyncio.iscoroutinefunction(fn):
            asyncio.run_coroutine_threadsafe(fn(member, license_info, points), bot.loop)
        else:
            bot.loop.call_soon_threadsafe(fn, member, license_info, points)

    except Exception as e:
        print(f"Error syncing to sheets: {e}")


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

    # Ensure newer columns exist (migration-safe)
    cur.execute("PRAGMA table_info(licenses)")
    cols = {row[1] for row in cur.fetchall()}

    if "license_type" not in cols:
        cur.execute("ALTER TABLE licenses ADD COLUMN license_type TEXT")
    if "license_code" not in cols:
        cur.execute("ALTER TABLE licenses ADD COLUMN license_code TEXT")

    conn.commit()


# ============================================================
# SEND TO DISCORD (UPDATED LOGIC)
# ============================================================

async def send_license_to_discord(img_data, filename, discord_id, license_type="official"):
    await bot.wait_until_ready()

    # Normalize license_type for our logic/styles
    license_type = (license_type or "official").lower().strip()
    if license_type in ("standard", "full", "official"):
        normalized_type = "official"
    elif license_type == "provisional":
        normalized_type = "provisional"
    else:
        normalized_type = "official"

    # Create separate file objects for DM and Channel (Discord needs fresh pointer)
    file_dm = discord.File(io.BytesIO(img_data), filename=filename)
    file_ch = discord.File(io.BytesIO(img_data), filename=filename)

    dm_success = False

    # --- 1. DM THE USER (PING THEM IN THE DM) ---
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

    # --- 2. SEND TO CHANNEL & MANAGE ROLES ---
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except:
            channel = None

    guild = None
    if channel and hasattr(channel, "guild"):
        guild = channel.guild
    else:
        # fallback: pick first guild the bot can see (best-effort)
        if bot.guilds:
            guild = bot.guilds[0]

    # Role management (best-effort even if logging channel is missing)
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
                    # Add provisional roles
                    if ROLE_PROV_1:
                        await member.add_roles(ROLE_PROV_1, reason="Provisional license generated")
                    if ROLE_PROV_2:
                        await member.add_roles(ROLE_PROV_2, reason="Provisional license generated")
                else:
                    # Official license:
                    # Remove provisional role 145468... and add official role 145507...
                    if ROLE_PROV_2:
                        await member.remove_roles(ROLE_PROV_2, reason="Upgraded to official license")
                    if ROLE_OFFICIAL:
                        await member.add_roles(ROLE_OFFICIAL, reason="Official license generated")
    except Exception as e:
        print(f"Role management error: {e}")

    # Channel log message
    if channel:
        status = "Check your DMs!" if dm_success else "Your DMs are closed, so I'm posting it here!"

        embed_ch = discord.Embed(
            description=f"**License Issued for <@{discord_id}>**\n{status}",
            color=0x3498db
        )
        embed_ch.set_image(url=f"attachment://{filename}")
        embed_ch.set_footer(text="DMV Registry System")

        await channel.send(content=f"<@{discord_id}>", embed=embed_ch, file=file_ch)


@bot.tree.command(name="getlicense", description="Retrieve your existing Lakeview license via DM")
async def getlicense(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM licenses WHERE discord_id = ?",
                (str(interaction.user.id),)
            )
            row = await cursor.fetchone()

        if not row:
            return await interaction.followup.send("❌ No license found in the system. Please apply first!", ephemeral=True)

        # Table order (after migration):
        # 0 discord_id
        # 1 roblox_username
        # 2 roblox_display
        # 3 roleplay_name
        # 4 age
        # 5 address
        # 6 eye_color
        # 7 height
        # 8 license_number
        # 9 issued_at
        # 10 expires_at
        # 11 license_type
        # 12 license_code

        avatar_url = interaction.user.display_avatar.url
        avatar_bytes = requests.get(avatar_url).content

        try:
            issued = datetime.fromisoformat(row[9]) if row[9] else datetime.utcnow()
            expires = datetime.fromisoformat(row[10]) if row[10] else issued + timedelta(days=150)
        except (ValueError, TypeError):
            issued = datetime.utcnow()
            expires = issued + timedelta(days=150)

        stored_type = (row[11] or "official").lower().strip()
        if stored_type in ("standard", "full", "official"):
            stored_type = "official"
        elif stored_type != "provisional":
            stored_type = "official"

        img = create_license_image(
            row[1], avatar_bytes, row[2], row[3], row[4],
            row[5], row[6], row[7], issued, expires, row[8], stored_type
        )

        filename = f"{row[1]}_license.png"
        file = discord.File(io.BytesIO(img), filename=filename)

        # DM content pings them
        dm_content = f"<@{interaction.user.id}>\nHere is your saved **{stored_type.title()}** license."
        embed = discord.Embed(title="License Retrieval", color=0x3498db)
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text="Lakeview City DMV Archive")

        await interaction.user.send(content=dm_content, embed=embed, file=file)
        await interaction.followup.send("✅ I have sent your license to your Direct-Messages!", ephemeral=True)

        # Optional: re-sync sheet on retrieval (keeps sheet consistent)
        license_code = row[12] if len(row) > 12 else None
        license_info = {
            "roblox_username": row[1],
            "roblox_display": row[2],
            "roleplay_name": row[3],
            "license_number": row[8],
            "license_type": stored_type,
            "license_code": license_code or "C",
        }
        _schedule_sheet_update(str(interaction.user.id), license_info, 0)

    except discord.Forbidden:
        await interaction.followup.send("❌ I couldn't DM you. Please open your Privacy Settings.", ephemeral=True)
    except Exception as e:
        print(e)
        await interaction.followup.send("❌ An error occurred while retrieving your license.", ephemeral=True)


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
        # normalize incoming type (so "standard"/"official"/"full" all behave as official)
        if incoming_type in ("standard", "official", "full"):
            license_type = "official"
        elif incoming_type == "provisional":
            license_type = "provisional"
        else:
            license_type = "official"

        license_code = data.get("license_code", "C")
        lic_num = data.get("license_number", username)

        if not username or not avatar:
            return jsonify({"status": "error", "message": "Missing username/avatar"}), 400

        avatar_bytes = requests.get(avatar).content

        issued = datetime.utcnow()
        if license_type == "provisional":
            expires = issued + timedelta(days=3)
        else:
            expires = issued + timedelta(days=150)

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
            lic_num,
            license_type
        )

        # Pass license_type to the async task
        bot.loop.create_task(
            send_license_to_discord(img, f"{username}_license.png", discord_id, license_type)
        )

        # ============================================================
        # SAVE LICENSE INFO INTO THE DATABASE
        # ============================================================

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
                discord_id,
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

        # ============================================================
        # SYNC TO GOOGLE SHEETS IMMEDIATELY
        # ============================================================

        license_info = {
            "roblox_username": username,
            "roblox_display": display,
            "roleplay_name": roleplay,
            "license_number": lic_num,
            "license_type": license_type,
            "license_code": license_code,
        }

        _schedule_sheet_update(str(discord_id), license_info, 0)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# SINGLE CORRECT SETUP HOOK
# ============================================================

async def setup_hook():
    # Create database BEFORE loading any extension that uses it
    bot.db = await aiosqlite.connect(DB_PATH)

    # Load other cogs - Wrapped in try/except to avoid crash if files miss
    extensions = [
        "cogs.erlc_application",
        "cogs.cad",
        "cogs.dmv",
        "cogs.dept roster",  # Fixed space in name usually unlikely in python imports
        "cogs.economy",
        "cogs.auto_giveaway",
        "cogs.blackmarket"
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
