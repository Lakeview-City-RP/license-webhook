
from __future__ import annotations

# --- stdlib ---
import os
import io
import math
import json
import time
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("license-bot")


class LicenseSystem(commands.Cog):
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

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Flask server
        self.app = Flask("license-system")
        self._flask_thread: Optional[Thread] = None

        # service account configuration
        self.SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
        self.SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        self.SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

        # register routes
        self._register_routes()

    # -------------------------
    # COG LOAD/UNLOAD
    # -------------------------
    async def cog_load(self):
        # Start Flask thread once
        if self._flask_thread is None:
            self._flask_thread = Thread(target=self._run_flask, daemon=True)
            self._flask_thread.start()
            log.info("✅ License Flask API started on 0.0.0.0:8080")

    async def cog_unload(self):
        # Flask cannot be cleanly stopped easily in dev server; ignore.
        pass

    # ============================================================
    # GOOGLE SHEETS HELPERS
    # ============================================================
    def _get_gspread_client(self) -> gspread.Client:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        if self.SERVICE_ACCOUNT_JSON:
            info = json.loads(self.SERVICE_ACCOUNT_JSON)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            sa_file = self.SERVICE_ACCOUNT_FILE
            if not os.path.exists(sa_file) and os.path.exists("google_service_account.json"):
                sa_file = "google_service_account.json"
            creds = Credentials.from_service_account_file(sa_file, scopes=scopes)

        return gspread.authorize(creds)

    def _open_spreadsheet(self, gc: gspread.Client) -> gspread.Spreadsheet:
        if self.SPREADSHEET_ID:
            return gc.open_by_key(self.SPREADSHEET_ID)
        return gc.open(self.SHEET_NAME)

    def _ensure_header(self, ws: gspread.Worksheet):
        header = ws.row_values(1)
        if header:
            return
        ws.append_row(
            [
                "Discord ID",
                "Roblox Username",
                "Roblox Display",
                "Roleplay Name",
                "License Number",
                "License Type",
                "License Code",
                "Issued (UTC)",
                "Expires (UTC)",
                "Last Updated (UTC)",
            ],
            value_input_option="USER_ENTERED",
        )

    def upsert_license_to_sheet(self, license_info: dict):
        for attempt in range(1, 4):
            try:
                gc = self._get_gspread_client()
                sh = self._open_spreadsheet(gc)
                ws = sh.worksheet(self.WORKSHEET_NAME)
                self._ensure_header(ws)

                discord_id = str(license_info.get("discord_id", "")).strip()
                if not discord_id:
                    raise ValueError("license_info.discord_id missing")

                now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

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

                col_a = ws.col_values(1)
                target_row_idx = None
                for idx, val in enumerate(col_a[1:], start=2):
                    if str(val).strip() == discord_id:
                        target_row_idx = idx
                        break

                if target_row_idx is None:
                    ws.append_row(row, value_input_option="USER_ENTERED")
                else:
                    ws.update(f"A{target_row_idx}:J{target_row_idx}", [row], value_input_option="USER_ENTERED")

                log.info("[Sheets] upserted license row for %s", discord_id)
                return

            except Exception as e:
                log.warning("[Sheets] attempt %s failed: %s", attempt, e)
                if attempt == 3:
                    return
                time.sleep(1.5 * attempt)

    def schedule_sheet_upsert(self, license_info: dict):
        Thread(target=self.upsert_license_to_sheet, args=(license_info,), daemon=True).start()

    # ============================================================
    # FONT / IMAGE
    # ============================================================
    def load_font(self, size: int, bold: bool = False):
        files = [
            ("arialbd.ttf" if bold else "arial.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for f in files:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def create_license_image(
        self,
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
        license_type,
    ):
        W, H = 820, 520

        username_str = str(username or "")
        roleplay_name_str = str(roleplay_name or username_str)
        age_str = str(age or "")
        addr_str = str(address or "")
        eye_str = str(eye_color or "")
        height_str = str(height or "")
        lic_num_str = str(lic_num or "")

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

            bgd.line((0, y, W, y), fill=(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))

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
            title_font = self.load_font(35, bold=True)
        else:
            header_color_start = (35, 70, 160)
            header_color_end = (60, 100, 190)
            title_text = "LAKEVIEW CITY DRIVER LICENSE"
            title_font = self.load_font(39, bold=True)

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
        except Exception:
            pass

        section = self.load_font(24, bold=True)
        boldf = self.load_font(22, bold=True)
        normal = self.load_font(22)

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

        buf = io.BytesIO()
        card.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    # ============================================================
    # DB HELPERS
    # ============================================================
    def _ensure_license_table_and_columns(self, conn: sqlite3.Connection):
        cur = conn.cursor()
        cur.execute(
            """
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
            """
        )
        conn.commit()

        cur.execute("PRAGMA table_info(licenses)")
        cols = {row[1] for row in cur.fetchall()}

        if "license_type" not in cols:
            cur.execute("ALTER TABLE licenses ADD COLUMN license_type TEXT")
        if "license_code" not in cols:
            cur.execute("ALTER TABLE licenses ADD COLUMN license_code TEXT")
        conn.commit()

    # ============================================================
    # SEND TO DISCORD
    # ============================================================
    async def send_license_to_discord(self, img_data: bytes, filename: str, discord_id: str, license_type: str = "official"):
        await self.bot.wait_until_ready()

        license_type = (license_type or "official").lower().strip()
        if license_type in ("standard", "full", "official"):
            normalized_type = "official"
        elif license_type == "provisional":
            normalized_type = "provisional"
        else:
            normalized_type = "official"

        uid = int(discord_id)

        channel = self.bot.get_channel(self.LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.LOG_CHANNEL_ID)
            except Exception:
                channel = None

        guild = None
        if isinstance(channel, discord.TextChannel) and channel.guild:
            guild = channel.guild
        elif self.bot.guilds:
            guild = self.bot.guilds[0]

        try:
            if guild:
                member = guild.get_member(uid)
                if not member:
                    try:
                        member = await guild.fetch_member(uid)
                    except Exception:
                        member = None

                if member:
                    role_prov_1 = guild.get_role(self.ROLE_PROV_1_ID)
                    role_prov_2 = guild.get_role(self.ROLE_PROV_2_ID)
                    role_official = guild.get_role(self.ROLE_OFFICIAL_ID)

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
            log.warning("Role management error for %s: %s", uid, e)

        if channel and hasattr(channel, "send"):
            file_ch = discord.File(io.BytesIO(img_data), filename=filename)

            if normalized_type == "provisional":
                embed = discord.Embed(
                    title="LKVC: Provisional License Generated",
                    description="> We have generated your provisional license, this needs to be added & updated onto your Sonoran CAD Character. You are now bound to our [provisional license regulations](https://docs.google.com/document/d/1F7tN0HrWWKe3GprX0TlzaqXd-1PAiA-3u3GLB0Q-wUU/edit?usp=sharing). Run `/dmv-points` to check your points. Also ensure to apply for a official license [here](https://discord.com/channels/1328475009542258688/1437618758440063128). .",
                    color=0xE67E22,
                )
            else:
                embed = discord.Embed(
                    title="LKVC: Official Drivers License",
                    description="> We have generated your official drivers license, please save this & upload it to Sonoran CAD. You are bound to all DMV [Road Regulations](https://docs.google.com/document/d/1fRGbl0cB_JQhPFLTxsQ65n2qzH2o37UsZmzJl-K1BVM/edit?usp=sharing). Your license may attain points via the [point system](https://docs.google.com/document/d/10ncyZktSIhbs3X9tY-Ru63cBpO08yMUY72IjDeTlBIU/edit?usp=sharing) or citations, you can check this by running `/dmv-points`. ",
                    color=0x2ECC71,
                )

            embed.set_image(url=f"attachment://{filename}")
            embed.set_footer(text="Lakeview City DMV • Official Document")
            await channel.send(content=f"<@{uid}>", embed=embed, file=file_ch)
        else:
            log.warning("LOG_CHANNEL_ID is invalid or not messageable (%s).", self.LOG_CHANNEL_ID)

    # ============================================================
    # FLASK ROUTES
    # ============================================================
    def _register_routes(self):
        @self.app.get("/")
        def home():
            return "OK", 200

        @self.app.route("/license", methods=["POST"])
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

                r = requests.get(avatar, timeout=15)
                r.raise_for_status()
                avatar_bytes = r.content

                issued = datetime.utcnow()
                expires = issued + (timedelta(days=3) if license_type == "provisional" else timedelta(days=150))

                img = self.create_license_image(
                    username, avatar_bytes, display, roleplay, age, addr, eye, height,
                    issued, expires, lic_num, license_type
                )

                # ✅ thread-safe schedule to bot loop
                fut = asyncio.run_coroutine_threadsafe(
                    self.send_license_to_discord(img, f"{username}_license.png", str(discord_id), license_type),
                    self.bot.loop,
                )

                def _done_cb(f: "asyncio.Future"):
                    exc = f.exception()
                    if exc:
                        log.error("[/license] send_license_to_discord failed: %s", exc)
                    else:
                        log.info("[/license] License posted for %s", discord_id)

                fut.add_done_callback(_done_cb)

                # Save to DB
                conn = sqlite3.connect(self.DB_PATH)
                self._ensure_license_table_and_columns(conn)
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

                # Google Sheets upsert
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
                self.schedule_sheet_upsert(license_info)

                return jsonify({"status": "ok"}), 200

            except Exception as e:
                import traceback
                log.error(traceback.format_exc())
                return jsonify({"status": "error", "message": str(e)}), 500

    def _run_flask(self):
        # Render uses PORT; locally 8080 is fine
        port = int(os.getenv("PORT", "8080"))
        self.app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(LicenseSystem(bot))
