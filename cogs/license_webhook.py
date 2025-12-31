from __future__ import annotations

import os
import io
import math
from datetime import datetime, timedelta, timezone

import aiosqlite
import requests
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from aiohttp import web


# -------------------------
# IMAGE (your function, unchanged)
# -------------------------
def load_font(size: int, bold: bool = False):
    files = [
        ("arialbd.ttf" if bold else "arial.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
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
    except Exception:
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

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# -------------------------
# COG
# -------------------------
class LicenseWebhook(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.port = int(os.getenv("PORT", "8080"))  # Render uses PORT
        self.license_channel_id = int(os.getenv("LICENSE_CHANNEL_ID", "1436890841703645285"))
        self.db_path = os.getenv("LICENSE_DB_PATH", "workforce.db")

        self.web_app = web.Application()
        self.web_app.router.add_get("/health", self.health)
        self.web_app.router.add_post("/license", self.license)

        self.runner = web.AppRunner(self.web_app)
        self.site: web.TCPSite | None = None

    async def cog_load(self):
        await self._ensure_db()
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await self.site.start()
        print(f"✅ License webhook listening on 0.0.0.0:{self.port}")

    async def cog_unload(self):
        await self.runner.cleanup()

    async def _ensure_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
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
            await db.commit()

    async def health(self, _request: web.Request):
        return web.json_response({"ok": True})

    async def _send_license_to_discord(self, img_data: bytes, filename: str, discord_id: str):
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
                    color=0x2ecc71
                )
                embed.set_image(url=f"attachment://{filename}")
                embed.set_footer(
                    text="Lakeview City DMV • Official Document",
                    icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
                )
                await user.send(embed=embed, file=file_dm)
                dm_success = True
        except Exception as e:
            print("DM failed:", e)

        channel = self.bot.get_channel(self.license_channel_id)
        if channel:
            status = "Check your DMs!" if dm_success else "Your DMs are closed, so I'm posting it here!"
            embed2 = discord.Embed(
                description=f"**License Issued for <@{discord_id}>**\n{status}",
                color=0x3498db
            )
            embed2.set_image(url=f"attachment://{filename}")
            embed2.set_footer(text="DMV Registry System")
            await channel.send(content=f"<@{discord_id}>", embed=embed2, file=file_ch)

    async def license(self, request: web.Request):
        try:
            data = await request.json()

            username = data.get("roblox_username")
            display = data.get("roblox_display")
            avatar = data.get("roblox_avatar")
            roleplay = data.get("roleplay_name")
            age = data.get("age")
            addr = data.get("address")
            eye = data.get("eye_color")
            height = data.get("height")
            discord_id = str(data.get("discord_id", "")).strip()
            license_type = str(data.get("license_type", "standard")).lower()
            license_code = str(data.get("license_code", "C"))
            lic_num = data.get("license_number", username)

            if not discord_id.isdigit():
                return web.json_response({"status": "error", "message": "discord_id missing/invalid"}, status=400)

            if not username or not avatar:
                return web.json_response({"status": "error", "message": "Missing username/avatar"}, status=400)

            # download avatar
            avatar_bytes = requests.get(avatar, timeout=10).content

            issued = datetime.now(timezone.utc)
            expires = issued + (timedelta(days=3) if license_type == "provisional" else timedelta(days=150))

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

            # Save to DB (no Google Sheets)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO licenses (
                        discord_id, roblox_username, roblox_display, roleplay_name,
                        age, address, eye_color, height,
                        license_number, issued_at, expires_at
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
                """, (
                    discord_id, username, display, roleplay,
                    str(age), str(addr), str(eye), str(height),
                    str(lic_num),
                    issued.isoformat(),
                    expires.isoformat(),
                ))
                await db.commit()

            # Send to Discord
            await self._send_license_to_discord(img, f"{username}_license.png", discord_id)

            return web.json_response({"status": "ok"})

        except Exception as e:
            print("LICENSE ERROR:", repr(e))
            return web.json_response({"status": "error", "message": str(e)}, status=500)


async def setup(bot: commands.Bot):
    await bot.add_cog(LicenseWebhook(bot))
