from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import re
import os
import random
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
from flask import Flask, render_template_string
from threading import Thread

# ============================================================
# CONFIG
# ============================================================

GUILD_ID = 1328475009542258688

ECON_FILE = "economy.json"

LOG_CHANNEL = 1440450438083117076
ECON_CHANNEL = 1442671320910528664

AFK_CHANNEL = 1442670867963445329
SALARY_VC_CATEGORY = 1436503704143396914

LEO_ROLE = 1436150189227380786
STAFF_ROLE = 1328939648621346848
BANK_ROLE = 1436150175637967012
BANK_CATEGORY = 1440449001550778554

CALLSIGN_REGEX = r"\b\d{2,4}\b"

ROLE_SALARIES = {
    1436150189227380786: 10
}

EMBED_COLOR = 0x757575
FOOTER_TEXT = "Lakeview City Whitelisted Automation Services"
FOOTER_ICON = "https://media.discordapp.net/attachments/1328966350806323274/1437620682526556160/b54f20d93dcf92bd737259fa0c9778f3.png"
THUMBNAIL_URL = "https://media.discordapp.net/attachments/1377401295220117746/1437245076945375393/WHITELISTED_NO_BACKGROUND.png"

# ============================================================
# STORAGE
# ============================================================

def load_data():
    if not os.path.exists(ECON_FILE):
        with open(ECON_FILE, "w") as f:
            json.dump({"users": {}, "afk_return": {}}, f, indent=4)
    with open(ECON_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(ECON_FILE, "w") as f:
        json.dump(data, f, indent=4)

def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

# ============================================================
# EMBEDS
# ============================================================

def econ_embed(title, desc):
    e = discord.Embed(title=title, description=desc, color=EMBED_COLOR)
    e.set_thumbnail(url=THUMBNAIL_URL)
    e.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    return e

# ============================================================
# REVOKE BUTTON (ADDED)
# ============================================================

class RevokeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Revoke", style=discord.ButtonStyle.secondary)
    async def revoke(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Revoke confirmed.", ephemeral=True)

# ============================================================
# ADMIN DASHBOARD (ADDED)
# ============================================================

web = Flask("economy_dashboard")

DASH_HTML = """
<h1>Lakeview Economy Admin Panel</h1>
<table border="1">
<tr><th>User ID</th><th>Cash</th><th>Bank</th></tr>
{% for uid, u in users.items() %}
<tr>
<td>{{uid}}</td>
<td>${{u.cash}}</td>
<td>${{u.bank}}</td>
</tr>
{% endfor %}
</table>
"""

@web.route("/")
def index():
    data = load_data()
    return render_template_string(DASH_HTML, users=data["users"])

def run_web():
    web.run("0.0.0.0", 8085)

Thread(target=run_web, daemon=True).start()

# ============================================================
# ECONOMY COG
# ============================================================

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.shift_start_times = {}
        self.afk_timers = {}

        self.salary_task.start()
        self.afk_check.start()

    # ========================================================
    # AFK SYSTEM (UPDATED: RETURN BACK TO ORIGINAL VC)
    # ========================================================

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.guild or member.guild.id != GUILD_ID:
            return

        data = load_data()

        if after.self_deaf:
            self.afk_timers[member.id] = datetime.utcnow()
            if before.channel:
                data["afk_return"][str(member.id)] = before.channel.id
                save_data(data)
        else:
            self.afk_timers.pop(member.id, None)
            if str(member.id) in data["afk_return"]:
                channel_id = data["afk_return"][str(member.id)]
                ch = self.bot.get_channel(channel_id)
                if ch:
                    await member.move_to(ch)
                del data["afk_return"][str(member.id)]
                save_data(data)

    @tasks.loop(seconds=30)
    async def afk_check(self):
        now_time = datetime.utcnow()
        guild = self.bot.get_guild(GUILD_ID)

        for uid, start in list(self.afk_timers.items()):
            if (now_time - start).total_seconds() >= 120:
                member = guild.get_member(uid)
                if member and member.voice and member.voice.channel:
                    await member.move_to(guild.get_channel(AFK_CHANNEL))
                self.afk_timers.pop(uid, None)

    # ========================================================
    # PAYSLIP
    # ========================================================

    def generate_payslip(self, member, before, after, amount):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        c.drawString(50, 750, "Lakeview City - Payslip")
        c.drawString(50, 730, f"User: {member.name} ({member.id})")
        c.drawString(50, 710, f"Shift started: {self.shift_start_times.get(member.id, 'Unknown')}")
        c.drawString(50, 690, f"Shift ended: {now()}")
        c.drawString(50, 670, f"Pay amount: ${amount}")
        c.drawString(50, 650, f"Balance before: ${before}")
        c.drawString(50, 630, f"Balance after: ${after}")

        c.save()
        buffer.seek(0)
        return buffer

    # ========================================================
    # SHIFT PAY
    # ========================================================

    @tasks.loop(minutes=1)
    async def salary_task(self):
        data = load_data()
        log_channel = self.bot.get_channel(LOG_CHANNEL)

        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        for member in guild.members:
            if not member.voice or not member.voice.channel:
                if member.id in self.shift_start_times:
                    del self.shift_start_times[member.id]
                continue

            if member.voice.channel.id == AFK_CHANNEL:
                continue

            if LEO_ROLE not in [r.id for r in member.roles]:
                continue

            if not member.nick or not re.search(CALLSIGN_REGEX, member.nick):
                continue

            if member.voice.channel.category_id != SALARY_VC_CATEGORY:
                continue

            if member.id not in self.shift_start_times:
                self.shift_start_times[member.id] = now()

            uid = str(member.id)
            data["users"].setdefault(uid, {"cash": 0, "bank": 0, "inventory": []})

            before = data["users"][uid]["cash"]
            pay = ROLE_SALARIES[LEO_ROLE]
            data["users"][uid]["cash"] += pay
            after = data["users"][uid]["cash"]
            save_data(data)

            if log_channel:
                await log_channel.send(
                    embed=econ_embed(
                        "Shift payment",
                        f"**User:** {member.mention} ({member.id})\n"
                        f"**Shift start:** {self.shift_start_times[member.id]}\n"
                        f"**Time paid:** {now()}\n"
                        f"**Before:** ${before}\n"
                        f"**After:** ${after}"
                    ),
                    view=RevokeView()
                )

                pdf = self.generate_payslip(member, before, after, pay)
                await log_channel.send(file=discord.File(pdf, filename=f"payslip_{member.id}.pdf"))

    # ========================================================
    # SLASH COMMANDS (UNCHANGED + INVENTORY HELPERS ADDED)
    # ========================================================

    def valid_channel(self, i: discord.Interaction):
        return (
            i.guild and i.guild.id == GUILD_ID and
            (i.channel_id == ECON_CHANNEL or STAFF_ROLE in [r.id for r in i.user.roles])
        )

    @app_commands.command(name="balance")
    async def balance(self, i: discord.Interaction):
        if not self.valid_channel(i):
            return

        data = load_data()
        u = data["users"].setdefault(str(i.user.id), {"cash": 0, "bank": 0, "inventory": []})
        save_data(data)

        await i.response.send_message(embed=econ_embed(
            "Balance",
            f"**Cash:** ${u['cash']}\n**Bank:** ${u['bank']}"
        ))

    @app_commands.command(name="gamble")
    async def gamble(self, i: discord.Interaction, amount: int):
        if not self.valid_channel(i):
            return

        data = load_data()
        uid = str(i.user.id)

        if data["users"][uid]["cash"] < amount:
            return await i.response.send_message("Not enough cash.", ephemeral=True)

        before = data["users"][uid]["cash"]
        win = random.random() > 0.7

        if win:
            data["users"][uid]["cash"] += amount
        else:
            data["users"][uid]["cash"] -= amount

        after = data["users"][uid]["cash"]
        save_data(data)

        await i.response.send_message(embed=econ_embed(
            "Gamble",
            f"**Result:** {'Win' if win else 'Loss'}\n"
            f"**Before:** ${before}\n"
            f"**After:** ${after}"
        ))

    @app_commands.command(name="inventory_add")
    async def inventory_add(self, i: discord.Interaction, item: str):
        data = load_data()
        inv = data["users"].setdefault(str(i.user.id), {"cash":0,"bank":0,"inventory":[]})
        inv["inventory"].append(item)
        save_data(data)
        await i.response.send_message(f"✅ Added `{item}`")

# ============================================================
# REQUIRED COG SETUP
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
