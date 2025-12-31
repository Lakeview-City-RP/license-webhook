from __future__ import annotations

import os
import io
import re
import json
import math
import time
import asyncio
import random
import string
import sqlite3
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

import aiosqlite
import requests
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import discord
from discord.ext import commands

# ============================================================
# CONFIG / CONSTANTS
# ============================================================

# Where the license gets posted (channel message)
LOG_CHANNEL_ID = 1436890841703645285

# Role IDs (same ones you had)
ROLE_PROV_1_ID = 1436150194726113330
ROLE_PROV_2_ID = 1454680487917256786
ROLE_OFFICIAL_ID = 1455075670907686912

DB_PATH = "workforce.db"

# Flask
PORT = int(os.getenv("PORT", "8080"))

# Discord token: env DISCORD_TOKEN or token.txt
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN and os.path.exists("token.txt"):
    with open("token.txt", "r", encoding="utf-8") as f:
        TOKEN = f.read().strip()

if not TOKEN:
    raise RuntimeError("❌ Discord token not found (DISCORD_TOKEN or token.txt).")

PREFIX = "?"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

app = Flask(__name__)

# ============================================================
# DB (licenses)
# ============================================================

LICENSE_COLUMNS = {
    "discord_id": "TEXT",
    "roblox_username": "TEXT",
    "roblox_display": "TEXT",
    "roleplay_name": "TEXT",
    "age": "TEXT",
    "address": "TEXT",
    "eye_color": "TEXT",
    "height": "TEXT",
    "license_number": "TEXT",
    "license_type": "TEXT",
    "license_code": "TEXT",
    "issued_at": "TEXT",
    "expires_at": "TEXT",
    "avatar_url": "TEXT",
}

def ensure_db_sync():
    """Create table + columns safely (sync for Flask thread startup)."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    # Ensure all columns exist
    cur.execute("PRAGMA table_info(licenses)")
    existing = {row[1] for row in cur.fetchall()}

    for col, col_type in LICENSE_COLUMNS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE licenses ADD COLUMN {col} {col_type}")

    # Make discord_id unique (best-effort)
    # SQLite can't add unique constraint easily if existing duplicates; ignore failures.
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_licenses_discord_id ON licenses(discord_id)")
    except Exception:
        pass

    con.commit()
    con.close()

async def upsert_license_async(license_info: dict):
    """Insert/update a license row by discord_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")

        cols = list(LICENSE_COLUMNS.keys())
        values = [str(license_info.get(c, "") if license_info.get(c) is not None else "") for c in cols]

        # Upsert: if discord_id exists update, else insert
        discord_id = str(license_info.get("discord_id", "")).strip()
        if not discord_id:
            raise ValueError("discord_id missing")

        cur = await db.execute("SELECT id FROM licenses WHERE discord_id = ?", (discord_id,))
        row = await cur.fetchone()

        if row:
            set_clause = ", ".join([f"{c}=?" for c in cols])
            await db.execute(f"UPDATE licenses SET {set_clause} WHERE discord_id = ?", (*values, discord_id))
        else:
            placeholders = ",".join(["?"] * len(cols))
            col_clause = ",".join(cols)
            await db.execute(f"INSERT INTO licenses ({col_clause}) VALUES ({placeholders})", values)

        await db.commit()

async def fetch_license_by_discord_id(discord_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM licenses WHERE discord_id = ?", (str(discord_id),))
        return await cur.fetchone()

# ============================================================
# IMAGE GENERATION
# ============================================================

def load_font(size: int, bold: bool = False):
    files = [
        ("arialbd.ttf" if bold else "arial.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for f in files:
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _safe(s: object) -> str:
    return str(s if s is not None else "").strip()

def create_license_image(
    roblox_username: str,
    avatar_bytes: bytes,
    roblox_display: str,
    roleplay_name: str,
    age: str,
    address: str,
    eye_color: str,
    height: str,
    issued: datetime,
    expires: datetime,
    lic_num: str,
    license_type: str,
):
    """
    Clean card-style license image.
    (No Google Sheets needed; only uses passed values.)
    """
    W, H = 820, 520
    license_type = _safe(license_type).lower()
    if license_type not in {"provisional", "official"}:
        license_type = "official"

    # Base rounded card
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), 120, fill=255)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    base.putalpha(mask)
    card = base.copy()

    # Background gradient
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / max(1, H - 1)
        if license_type == "provisional":
            r = int(255 - 60 * t)
            g = int(170 + 30 * t)
            b = int(70 - 50 * t)
        else:
            r = int(150 + 40 * t)
            g = int(180 + 55 * t)
            b = int(220 + 25 * t)
        bgd.line((0, y, W, y), fill=(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), 255))

    # Subtle pattern overlay
    pattern = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pattern)
    pcol = (255, 255, 255, 35) if license_type == "official" else (255, 180, 100, 45)
    for x in range(0, W, 42):
        for y in range(0, H, 42):
            pd.arc((x, y, x + 84, y + 84), 0, 180, fill=pcol, width=2)
    pattern = pattern.filter(ImageFilter.GaussianBlur(1.2))
    bg.alpha_composite(pattern)

    bg.putalpha(mask)
    card = Image.alpha_composite(card, bg)
    draw = ImageDraw.Draw(card)

    # Header bar
    header_h = 84
    header = Image.new("RGBA", (W, header_h), (255, 255, 255, 90))
    card.alpha_composite(header, (0, 0))

    title_font = load_font(30, bold=True)
    small_font = load_font(18, bold=False)
    label_font = load_font(16, bold=True)
    value_font = load_font(18, bold=False)

    title = "LAKEVIEW CITY DMV"
    draw.text((34, 22), title, font=title_font, fill=(10, 10, 10, 255))

    type_badge = "PROVISIONAL" if license_type == "provisional" else "OFFICIAL"
    badge_w = 190
    badge_h = 40
    badge_x = W - badge_w - 28
    badge_y = 22
    badge_color = (230, 126, 34, 230) if license_type == "provisional" else (46, 204, 113, 230)
    ImageDraw.Draw(card).rounded_rectangle(
        (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
        18,
        fill=badge_color
    )
    draw.text((badge_x + 18, badge_y + 10), type_badge, font=label_font, fill=(255, 255, 255, 255))

    # Avatar circle
    avatar_size = 168
    ax, ay = 40, 124
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        av = av.resize((avatar_size, avatar_size))
    except Exception:
        av = Image.new("RGBA", (avatar_size, avatar_size), (200, 200, 200, 255))

    circle = Image.new("L", (avatar_size, avatar_size), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, avatar_size, avatar_size), fill=255)
    av.putalpha(circle)

    # Drop shadow
    shadow = Image.new("RGBA", (avatar_size + 12, avatar_size + 12), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((6, 6, avatar_size + 6, avatar_size + 6), fill=(0, 0, 0, 80))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    card.alpha_composite(shadow, (ax - 6, ay - 6))
    card.alpha_composite(av, (ax, ay))

    # Text fields
    left_x = 240
    top_y = 130
    line_gap = 52

    fields = [
        ("Roblox Username", roblox_username),
        ("Display Name", roblox_display),
        ("Roleplay Name", roleplay_name),
        ("Age", age),
        ("Address", address),
        ("Eye Color", eye_color),
        ("Height", height),
    ]

    def draw_field(i: int, label: str, value: str):
        y = top_y + i * line_gap
        draw.text((left_x, y), f"{label}:", font=label_font, fill=(20, 20, 20, 230))
        draw.text((left_x + 170, y), _safe(value), font=value_font, fill=(0, 0, 0, 255))

    for i, (lab, val) in enumerate(fields):
        draw_field(i, lab, val)

    # Bottom info row
    bottom_y = H - 88
    draw.line((34, bottom_y - 18, W - 34, bottom_y - 18), fill=(255, 255, 255, 150), width=2)

    issued_s = issued.strftime("%Y-%m-%d")
    expires_s = expires.strftime("%Y-%m-%d")

    draw.text((34, bottom_y), f"License No: {_safe(lic_num)}", font=label_font, fill=(0, 0, 0, 240))
    draw.text((34, bottom_y + 26), f"Issued: {issued_s}   Expires: {expires_s}", font=small_font, fill=(0, 0, 0, 210))

    draw.text((W - 300, bottom_y), "DMV Registry System", font=label_font, fill=(0, 0, 0, 200))
    draw.text((W - 300, bottom_y + 26), "Official Document", font=small_font, fill=(0, 0, 0, 200))

    # Export to PNG bytes
    out = io.BytesIO()
    card.convert("RGBA").save(out, format="PNG")
    return out.getvalue()

# ============================================================
# DISCORD SENDING
# ============================================================

def _normalize_type(s: str) -> str:
    s = _safe(s).lower()
    if s in {"provisional", "prov", "p"}:
        return "provisional"
    if s in {"official", "standard", "full", "o"}:
        return "official"
    return "official"

async def send_license_to_discord(license_info: dict, img_data: bytes):
    discord_id = str(license_info["discord_id"])
    normalized_type = _normalize_type(license_info.get("license_type", "official"))

    filename = f"{license_info.get('roblox_username','user')}_license.png".replace(" ", "_")
    file_dm = discord.File(io.BytesIO(img_data), filename=filename)
    file_ch = discord.File(io.BytesIO(img_data), filename=filename)

    # 1) DM user
    dm_success = False
    try:
        user = await bot.fetch_user(int(discord_id))
        if user:
            if normalized_type == "provisional":
                dm_content = f"<@{discord_id}>\n✅ Your **Provisional License** has been generated. The image is attached below."
                embed_dm = discord.Embed(
                    title="🔰 Provisional License Issued",
                    description="Please follow all learner / provisional restrictions while driving.",
                    color=0xE67E22
                )
            else:
                dm_content = f"<@{discord_id}>\n✅ Your **Official License** has been generated. The image is attached below."
                embed_dm = discord.Embed(
                    title="🪪 Official Lakeview City License",
                    description="Your license has been recorded in the DMV system.",
                    color=0x2ECC71
                )

            embed_dm.set_image(url=f"attachment://{filename}")
            embed_dm.set_footer(text="Lakeview City DMV • Official Document")
            await user.send(content=dm_content, embed=embed_dm, file=file_dm)
            dm_success = True
    except Exception as e:
        print(f"Failed to DM user: {e}")

    # 2) Channel + roles
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception:
            channel = None

    guild = getattr(channel, "guild", None) if channel else (bot.guilds[0] if bot.guilds else None)

    # roles
    try:
        if guild:
            member = guild.get_member(int(discord_id))
            if not member:
                try:
                    member = await guild.fetch_member(int(discord_id))
                except Exception:
                    member = None

            if member:
                role_prov_1 = guild.get_role(ROLE_PROV_1_ID)
                role_prov_2 = guild.get_role(ROLE_PROV_2_ID)
                role_official = guild.get_role(ROLE_OFFICIAL_ID)

                if normalized_type == "provisional":
                    if role_prov_1:
                        await member.add_roles(role_prov_1, reason="Provisional license generated")
                    if role_prov_2:
                        await member.add_roles(role_prov_2, reason="Provisional license generated")
                else:
                    if role_prov_2:
                        await member.remove_roles(role_prov_2, reason="Upgraded to official license")
                    if role_official:
                        await member.add_roles(role_official, reason="Official license generated")
    except Exception as e:
        print(f"Role management error: {e}")

    if channel:
        status = "Check your DMs!" if dm_success else "Your DMs are closed, so I'm posting it here!"
        embed_ch = discord.Embed(
            description=f"**License Issued for <@{discord_id}>**\n{status}",
            color=0x3498DB
        )
        embed_ch.set_image(url=f"attachment://{filename}")
        embed_ch.set_footer(text="DMV Registry System")
        await channel.send(content=f"<@{discord_id}>", embed=embed_ch, file=file_ch)

def schedule_on_bot_loop(coro: asyncio.coroutine):
    """Schedule a coroutine onto the running discord loop from Flask thread."""
    try:
        loop = bot.loop
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            # If loop not running yet, this will fail; just log
            print("Discord loop not running yet; cannot schedule task.")
    except Exception as e:
        print(f"Failed scheduling coroutine: {e}")

# ============================================================
# DISCORD COMMAND: /getlicense
# ============================================================

@bot.tree.command(name="getlicense", description="Retrieve your existing Lakeview license via DM")
async def getlicense(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        row = await fetch_license_by_discord_id(str(interaction.user.id))
        if not row:
            return await interaction.followup.send("❌ No license found. Please apply first!", ephemeral=True)

        # We don’t rely on column order from SELECT *; we read by name safely.
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM licenses WHERE discord_id = ?", (str(interaction.user.id),))
            r = await cur.fetchone()

        issued = datetime.fromisoformat(r["issued_at"]) if r["issued_at"] else datetime.utcnow()
        expires = datetime.fromisoformat(r["expires_at"]) if r["expires_at"] else (issued + timedelta(days=365))

        avatar_url = interaction.user.display_avatar.url
        avatar_bytes = requests.get(avatar_url, timeout=15).content

        img_data = create_license_image(
            r["roblox_username"],
            avatar_bytes,
            r["roblox_display"],
            r["roleplay_name"],
            r["age"],
            r["address"],
            r["eye_color"],
            r["height"],
            issued,
            expires,
            r["license_number"],
            r["license_type"] or "official",
        )

        filename = f"{r['roblox_username']}_license.png".replace(" ", "_")
        file = discord.File(io.BytesIO(img_data), filename=filename)

        embed = discord.Embed(title="🪪 License Retrieval", color=0x3498DB)
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text="Lakeview City DMV Archive")

        await interaction.user.send(embed=embed, file=file)
        await interaction.followup.send("✅ I DM’d your license to you.", ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send("❌ I couldn't DM you. Please enable DMs and try again.", ephemeral=True)
    except Exception as e:
        print(e)
        await interaction.followup.send("❌ Error retrieving license.", ephemeral=True)

# ============================================================
# FLASK API
# ============================================================

def _rand_license_number() -> str:
    return "LKV-" + "".join(random.choices(string.digits, k=8))

def _rand_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

@app.get("/health")
def health():
    return jsonify({"ok": True}), 200

@app.post("/license")
def license_endpoint():
    """
    Expected JSON keys (same idea as before):
      roblox_username, roblox_display, roblox_avatar, roleplay_name, age, address, eye_color, height, discord_id
      license_type (optional: provisional/official)
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        discord_id = str(data.get("discord_id", "")).strip()
        if not discord_id or not discord_id.isdigit():
            return jsonify({"status": "error", "message": "discord_id missing/invalid"}), 400

        roblox_username = _safe(data.get("roblox_username"))
        roblox_display = _safe(data.get("roblox_display"))
        roleplay_name = _safe(data.get("roleplay_name")) or roblox_username
        age = _safe(data.get("age"))
        address = _safe(data.get("address"))
        eye_color = _safe(data.get("eye_color"))
        height = _safe(data.get("height"))

        avatar_url = _safe(data.get("roblox_avatar"))
        if not avatar_url:
            # fallback: we can still generate without avatar
            avatar_bytes = b""
        else:
            try:
                avatar_bytes = requests.get(avatar_url, timeout=15).content
            except Exception:
                avatar_bytes = b""

        license_type = _normalize_type(_safe(data.get("license_type", "official")))

        issued = datetime.utcnow()
        expires = issued + (timedelta(days=30) if license_type == "provisional" else timedelta(days=365))

        license_number = _rand_license_number()
        license_code = _rand_code()

        license_info = {
            "discord_id": discord_id,
            "roblox_username": roblox_username,
            "roblox_display": roblox_display,
            "roleplay_name": roleplay_name,
            "age": age,
            "address": address,
            "eye_color": eye_color,
            "height": height,
            "license_number": license_number,
            "license_type": license_type,
            "license_code": license_code,
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
            "avatar_url": avatar_url,
        }

        # Save to DB
        asyncio.run(upsert_license_async(license_info))

        # Generate image + send to Discord
        img_data = create_license_image(
            roblox_username,
            avatar_bytes,
            roblox_display,
            roleplay_name,
            age,
            address,
            eye_color,
            height,
            issued,
            expires,
            license_number,
            license_type,
        )

        schedule_on_bot_loop(send_license_to_discord(license_info, img_data))

        return jsonify({"status": "ok", "license_number": license_number, "license_code": license_code}), 200

    except Exception as e:
        print("License endpoint error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# STARTUP
# ============================================================

def run_flask():
    # Render expects 0.0.0.0 and PORT
    app.run(host="0.0.0.0", port=PORT, debug=False)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Slash sync error:", e)
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

def main():
    ensure_db_sync()
    Thread(target=run_flask, daemon=True).start()
    bot.run(TOKEN)

if __name__ == "__main__":
    main()
