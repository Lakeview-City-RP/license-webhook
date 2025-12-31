from __future__ import annotations

import os
import io
import math
import sqlite3
import asyncio
from datetime import datetime, timedelta
from threading import Thread

import aiosqlite
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import Flask, request, jsonify

import discord
from discord.ext import commands
from discord import app_commands


LICENSE_POST_CHANNEL_ID = 1436890841703645285
DB_PATH = "workforce.db"


def load_font(size: int, bold: bool = False):
    files = [
        ("arialbd.ttf" if bold else "arial.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for f in files:
        try:
            return ImageFont.truetype(f, size)
        except Exception:
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
    issued: datetime,
    expires: datetime,
    lic_num,
    license_type: str,
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

    # Background gradient
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
        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        bgd.line((0, y, W, y), fill=(r, g, b))

    # Mesh pattern
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

    # Header bar
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

    # Avatar
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((200, 200))
        m = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, 200, 200), 42, fill=255)
        av.putalpha(m)

        shadow = av.filter(ImageFilter.GaussianBlur(4))
        card.alpha_composite(shadow, (58, 158))
        card.alpha_composite(av, (50, 150))
    except Exception as e:
        print("Avatar render error:", e)

    # Fonts/colors
    section = load_font(24, bold=True)
    boldf = load_font(22, bold=True)
    normal = load_font(22)

    blue = (160, 70, 20) if license_type == "provisional" else (50, 110, 200)
    grey = (35, 35, 35)

    def ot(x, y, txt, font, fill):
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + ox, y + oy), txt, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), txt, font=font, fill=fill)

    # Identity section
    ix, iy = 290, 160
    ot(ix, iy, "IDENTITY:", section, blue)
    draw.line((ix, iy + 34, ix + 250, iy + 34), fill=blue, width=3)

    iy += 55

    def wp(x, y, label, value):
        lw = draw.textlength(label, font=boldf)
        draw.text((x, y), label, font=boldf, fill=grey)
        draw.text((x + lw + 10, y), str(value or ""), font=normal, fill=grey)

    wp(ix, iy, "Name:", roleplay_name_str)
    wp(ix, iy + 34, "Age:", age_str)
    wp(ix, iy + 68, "Address:", addr_str)

    # Physical section
    px, py = 550, 160
    ot(px, py, "PHYSICAL:", section, blue)
    draw.line((px, py + 34, px + 250, py + 34), fill=blue, width=3)

    py += 55
    wp(px, py, "Eye Color:", eye_str)
    wp(px, py + 34, "Height:", height_str)

    # DMV info box
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

    # Seal
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


class DMVApiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.app = Flask("dmv_api")

        self._ensure_db()

        # Routes
        self.app.add_url_rule("/", "health", self.healthcheck, methods=["GET"])
        self.app.add_url_rule("/license", "license", self.license_endpoint, methods=["POST"])

        # Start Flask in background thread
        self._flask_thread = Thread(target=self._run_flask, daemon=True)
        self._flask_thread.start()
        print("[DMVApiCog] Flask thread started")

    # -----------------------------
    # DB schema safety
    # -----------------------------
    def _ensure_db(self):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Minimal table creation that matches your INSERT/UPSERT
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                discord_id     TEXT PRIMARY KEY,
                roblox_username TEXT,
                roblox_display  TEXT,
                roleplay_name   TEXT,
                age             TEXT,
                address         TEXT,
                eye_color       TEXT,
                height          TEXT,
                license_number  TEXT,
                issued_at       TEXT,
                expires_at      TEXT
            )
            """
        )

        conn.commit()
        conn.close()

    # -----------------------------
    # Flask server
    # -----------------------------
    def _run_flask(self):
        # Render requires listening on PORT env var for web services
        port = int(os.environ.get("PORT", "8080"))
        self.app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    def healthcheck(self):
        return "OK", 200

    # -----------------------------
    # Discord sending
    # -----------------------------
    async def send_license_to_discord(self, img_data: bytes, filename: str, discord_id: str):
        await self.bot.wait_until_ready()

        file_dm = discord.File(io.BytesIO(img_data), filename=filename)
        file_ch = discord.File(io.BytesIO(img_data), filename=filename)

        dm_success = False
        try:
            user = await self.bot.fetch_user(int(discord_id))
            if user:
                embed = discord.Embed(
                    title="🪪 Official Lakeview City License",
                    description="Your driver license has been processed and is ready for use.",
                    color=0x2ecc71,
                )
                embed.set_image(url=f"attachment://{filename}")
                embed.set_footer(
                    text="Lakeview City DMV • Official Document",
                    icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None,
                )
                await user.send(embed=embed, file=file_dm)
                dm_success = True
        except Exception as e:
            print("[DMVApiCog] DM send error:", e)

        # Post fallback/registry
        channel = self.bot.get_channel(LICENSE_POST_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(LICENSE_POST_CHANNEL_ID)
            except Exception as e:
                print("[DMVApiCog] Channel fetch error:", e)
                return

        status = "Check your DMs!" if dm_success else "Your DMs are closed, so I'm posting it here!"
        embed = discord.Embed(
            description=f"**License Issued for <@{discord_id}>**\n{status}",
            color=0x3498db,
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text="DMV Registry System")

        await channel.send(content=f"<@{discord_id}>", embed=embed, file=file_ch)

    # -----------------------------
    # Flask endpoint
    # -----------------------------
    def license_endpoint(self):
        try:
            if not self.bot.is_ready():
                return jsonify({"status": "error", "message": "Bot not ready yet"}), 503

            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                data = request.form.to_dict() if request.form else {}

            if not data:
                return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

            # Expected fields (matches your BotGhost body)
            username = data.get("roblox_username")
            display = data.get("roblox_display")
            avatar = data.get("roblox_avatar")
            roleplay = data.get("roleplay_name")
            age = data.get("age")
            addr = data.get("address")
            eye = data.get("eye_color")
            height = data.get("height")
            discord_id = data.get("discord_id")
            license_type = (data.get("license_type") or "standard").lower()
            license_code = data.get("license_code", "C")  # optional
            lic_num = data.get("license_number") or username

            missing = []
            if not username:
                missing.append("roblox_username")
            if not avatar:
                missing.append("roblox_avatar")
            if not discord_id:
                missing.append("discord_id")
            if missing:
                return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

            # Fetch avatar safely
            r = requests.get(
                avatar,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code != 200:
                return jsonify({"status": "error", "message": f"Avatar fetch failed: HTTP {r.status_code}"}), 400
            avatar_bytes = r.content

            issued = datetime.utcnow()
            expires = issued + (timedelta(days=3) if license_type == "provisional" else timedelta(days=150))

            img = create_license_image(
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
                lic_num=lic_num,
                license_type=license_type,
            )

            # Thread-safe schedule into discord loop
            asyncio.run_coroutine_threadsafe(
                self.send_license_to_discord(img, f"{username}_license.png", str(discord_id)),
                self.bot.loop,
            )

            # Save/update DB
            conn = sqlite3.connect(DB_PATH)
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
                    expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    expires_at      = excluded.expires_at
                """,
                (
                    str(discord_id),
                    username,
                    display,
                    roleplay,
                    str(age) if age is not None else "",
                    str(addr) if addr is not None else "",
                    str(eye) if eye is not None else "",
                    str(height) if height is not None else "",
                    str(lic_num) if lic_num is not None else "",
                    issued.isoformat(),
                    expires.isoformat(),
                ),
            )
            conn.commit()
            conn.close()

            return jsonify({"status": "ok"}), 200

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return jsonify({"status": "error", "message": str(e)}), 500

    # -----------------------------
    # Slash command: /getlicense
    # -----------------------------
    @app_commands.command(name="getlicense", description="Retrieve your existing Lakeview license via DM")
    async def getlicense(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT * FROM licenses WHERE discord_id = ?",
                    (str(interaction.user.id),),
                )
                row = await cursor.fetchone()

            if not row:
                return await interaction.followup.send(
                    "❌ No license found in the system. Please apply first!",
                    ephemeral=True,
                )

            # Schema indices:
            # 0 discord_id, 1 roblox_username, 2 roblox_display, 3 roleplay_name, 4 age, 5 address
            # 6 eye_color, 7 height, 8 license_number, 9 issued_at, 10 expires_at
            issued = datetime.fromisoformat(row[9])
            expires = datetime.fromisoformat(row[10])

            avatar_url = interaction.user.display_avatar.url
            rr = requests.get(avatar_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if rr.status_code != 200:
                return await interaction.followup.send(
                    f"❌ Could not fetch your avatar (HTTP {rr.status_code}). Try again.",
                    ephemeral=True,
                )

            img = create_license_image(
                username=row[1],
                avatar_bytes=rr.content,
                display_name=row[2],
                roleplay_name=row[3],
                age=row[4],
                address=row[5],
                eye_color=row[6],
                height=row[7],
                issued=issued,
                expires=expires,
                lic_num=row[8],
                license_type="standard",
            )

            filename = f"{row[1]}_license.png"
            file = discord.File(io.BytesIO(img), filename=filename)

            embed = discord.Embed(title="License Retrieval", color=0x3498db)
            embed.set_image(url=f"attachment://{filename}")
            embed.set_footer(text="Lakeview City DMV Archive")

            await interaction.user.send(embed=embed, file=file)
            await interaction.followup.send("✅ Sent your license to your DMs!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I couldn't DM you. Please open your Privacy Settings.",
                ephemeral=True,
            )
        except Exception as e:
            print("[DMVApiCog] getlicense error:", e)
            await interaction.followup.send(
                "❌ An error occurred while retrieving your license.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(DMVApiCog(bot))
