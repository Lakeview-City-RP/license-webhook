from __future__ import annotations

# --- stdlib
import os, io, json, asyncio, hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# --- third-party
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# --- discord.py
import discord
from discord.ext import commands
from discord import ui

# --- config
from config import TOKEN, GUILD_ID  # and optionally STAFF_CHANNEL_ID if you want it here too

# ========= BOT SETUP =========
PREFIX = "?"
LICENSES_DIR = "licenses"
JSON_FILE = "licenses.json"
EXPIRATION_YEARS = 4
UNLIMITED_CREATORS = {934850555728252978, 1303898031032373309}
BLOXLINK_DEBUG = False

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

os.makedirs(LICENSES_DIR, exist_ok=True)
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

# ---------- JSON HELPERS ----------
def load_licenses():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_licenses(data):
    tmp = JSON_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, JSON_FILE)

def get_license_record(user_id: int):
    return load_licenses().get(str(user_id))

def save_license_record(user_id: int, record: dict):
    data = load_licenses()
    data[str(user_id)] = record
    save_licenses(data)

# ---------- BLOXLINK ----------
async def fetch_bloxlink(discord_id: int, guild_id: Optional[int] = None):
    guild_id = guild_id or GUILD_ID
    url = f"https://api.blox.link/v4/public/guilds/{guild_id}/discord-to-roblox/{discord_id}"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url, headers=headers) as resp:
                body = await resp.text()
                if BLOXLINK_DEBUG:
                    print(f"[BLOXLINK DEBUG] {resp.status} {url}  BODY~ {body[:250]}")
                if resp.status in (400, 404):
                    return None, None, "not_verified"
                if resp.status == 200:
                    j = await resp.json()
                    rid = j.get("robloxID")
                    username = j.get("resolved", {}).get("roblox", {}).get("username")
                    return rid, username, "bloxlink"
                return None, None, f"status_{resp.status}"
    except Exception as e:
        if BLOXLINK_DEBUG: print("[BLOXLINK ERROR]", e)
        return None, None, "error"

async def fetch_roblox_username(roblox_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://users.roblox.com/v1/users/{roblox_id}", timeout=8) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    return j.get("name") or j.get("displayName")
    except: pass
    return None

async def fetch_roblox_avatar(roblox_id: int):
    try:
        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={roblox_id}&size=420x420&format=Png"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=8) as resp:
                if resp.status == 200:
                    return await resp.read()
    except: pass
    return None

async def fetch_roblox_description(roblox_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://users.roblox.com/v1/users/{roblox_id}", timeout=8) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("description") or ""
    except: pass
    return ""

# ---------- LICENSE IMAGE ----------
def create_license_image(username, avatar_bytes, fields, issued, expires, lic_num, description):
    W, H = 1000, 620
    img = Image.new("RGBA", (W, H), (30, 31, 34, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 44)
        font_label = ImageFont.truetype("arial.ttf", 22)
        font_value = ImageFont.truetype("arialbd.ttf", 26)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_title = font_label = font_value = font_small = ImageFont.load_default()

    draw.rectangle((0, 0, W, 120), fill=(52, 56, 66))
    tw, _ = draw.textsize(username, font=font_title)
    draw.text(((W - tw) / 2, 35), f"{username} • City License", fill="white", font=font_title)

    av_x, av_y, av_size = 60, 160, 260
    draw.rounded_rectangle((av_x - 6, av_y - 6, av_x + av_size + 6, av_y + av_size + 6),
                           radius=20, fill=(60, 64, 72))
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((av_size, av_size))
            mask = Image.new("L", (av_size, av_size), 0)
            m = ImageDraw.Draw(mask); m.rounded_rectangle((0, 0, av_size, av_size), radius=18, fill=255)
            img.paste(avatar, (av_x, av_y), mask)
        except:
            draw.rectangle((av_x, av_y, av_x + av_size, av_y + av_size), fill=(110, 110, 110))

    x, y = av_x + av_size + 70, av_y
    for k in ["Full Name", "DOB", "Address", "Eye Color", "Height"]:
        v = fields.get(k, "N/A")
        draw.text((x, y), f"{k}:", fill="#adb5bd", font=font_label)
        draw.text((x + 170, y), v, fill="white", font=font_value)
        y += 40

    y += 12
    draw.text((x, y), "License #", fill="#adb5bd", font=font_label)
    draw.text((x + 170, y), lic_num, fill="white", font=font_value); y += 40
    draw.text((x, y), "Issued", fill="#adb5bd", font=font_label)
    draw.text((x + 170, y), issued.strftime("%Y-%m-%d"), fill="white", font=font_value); y += 40
    draw.text((x, y), "Expires", fill="#adb5bd", font=font_label)
    draw.text((x + 170, y), expires.strftime("%Y-%m-%d"), fill="white", font=font_value)

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG")
    out.seek(0)
    return out.read()

# ---------- LICENSE COMMANDS ----------
@bot.command()
async def license(ctx):
    await ctx.send("✅ License system is ready.")
    try:
        await ctx.message.delete()
    except:
        pass

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

if __name__ == "__main__":
    bot.run(TOKEN)
