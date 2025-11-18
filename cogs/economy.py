import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import re
import random
import os

# ============================================================
# CONFIGURATION — ALL SETTINGS PROVIDED BY YOU
# ============================================================

ECON_FILE = "economy.json"

# Salary logic
SALARY_VC_CATEGORY = 1436503704143396914
SALARY_ROLE = 1436150189227380786
SALARY_AMOUNT = 10

# Patterns
CALLSIGN_REGEX = r"\b\d{2,4}\b"

# Pay approval system
PAY_APPROVAL_CHANNEL = 1440448634591121601
PAY_STAFF_ROLE = 1328939648621346848

# Loan workflow
BANK_ROLE = 1436150175637967012
BANK_TICKET_CATEGORY = 1440449001550778554

# Logging channel (no emojis)
LOG_CHANNEL = 1440450438083117076

# Embed formatting
EMBED_COLOR = 0x757575
FOOTER_TEXT = "Lakeview City Whitelisted Automation Services"
FOOTER_ICON = "https://media.discordapp.net/attachments/1328966350806323274/1437620682526556160/b54f20d93dcf92bd737259fa0c9778f3.png"
THUMBNAIL_URL = "https://media.discordapp.net/attachments/1377401295220117746/1437245076945375393/WHITELISTED_NO_BACKGROUND.png"


# ============================================================
# UTILITY: LOAD + SAVE JSON
# ============================================================

def load_data():
    if not os.path.exists(ECON_FILE):
        with open(ECON_FILE, "w") as f:
            json.dump({"users": {}}, f, indent=4)
    with open(ECON_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(ECON_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ============================================================
# EMBED GENERATOR (MODERN LOOK)
# ============================================================

def modern_embed(title=None, description=None):
    embed = discord.Embed(
        title=title if title else None,
        description=description if description else None,
        color=EMBED_COLOR
    )
    embed.set_thumbnail(url=THUMBNAIL_URL)
    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    return embed


# ============================================================
# BUTTON VIEWS
# ============================================================

class PayApprovalView(discord.ui.View):
    def __init__(self, bot, sender_id, target_id, amount):
        super().__init__(timeout=None)
        self.bot = bot
        self.sender_id = sender_id
        self.target_id = target_id
        self.amount = amount

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if PAY_STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission to approve this.", ephemeral=True)

        data = load_data()
        sender = str(self.sender_id)
        target = str(self.target_id)

        if data["users"][sender]["cash"] < self.amount:
            return await interaction.response.send_message("Sender no longer has enough money.", ephemeral=True)

        data["users"][sender]["cash"] -= self.amount
        data["users"][target]["cash"] += self.amount
        save_data(data)

        embed = modern_embed("Payment Approved")
        embed.description = (
            "────────────\n"
            f"**Sender:** <@{self.sender_id}>\n"
            f"**Receiver:** <@{self.target_id}>\n"
            f"**Amount:** ${self.amount}\n"
            "────────────"
        )

        await interaction.response.edit_message(embed=embed, view=None)

        # Log
        log = interaction.client.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("PAYMENT APPROVED (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"Moderator: {interaction.user.mention}\n"
            f"From: <@{self.sender_id}>\n"
            f"To: <@{self.target_id}>\n"
            f"Amount: ${self.amount}\n"
            "────────────"
        )
        await log.send(embed=log_embed)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if PAY_STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You do not have permission to deny this.", ephemeral=True)

        embed = modern_embed("Payment Denied")
        embed.description = (
            "────────────\n"
            f"Request from <@{self.sender_id}> denied.\n"
            "────────────"
        )

        await interaction.response.edit_message(embed=embed, view=None)

        # Log
        log = interaction.client.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("PAYMENT DENIED (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"Moderator: {interaction.user.mention}\n"
            f"Sender: <@{self.sender_id}>\n"
            f"Target: <@{self.target_id}>\n"
            f"Amount: ${self.amount}\n"
            "────────────"
        )
        await log.send(embed=log_embed)


class LoanApprovalView(discord.ui.View):
    def __init__(self, bot, user_id, amount, ticket_channel):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.amount = amount
        self.ticket_channel = ticket_channel

    @discord.ui.button(label="Approve Loan", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if BANK_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You are not bank staff.", ephemeral=True)

        data = load_data()
        uid = str(self.user_id)

        data["users"][uid]["cash"] += self.amount
        data["users"][uid]["debt"] += self.amount
        save_data(data)

        embed = modern_embed("Loan Approved")
        embed.description = (
            "────────────\n"
            f"Loan approved for <@{self.user_id}>.\n"
            f"Amount: ${self.amount}\n"
            "────────────"
        )
        await interaction.response.edit_message(embed=embed, view=None)

        log = interaction.client.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("LOAN APPROVED (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"Bank Staff: {interaction.user.mention}\n"
            f"User: <@{self.user_id}>\n"
            f"Amount: ${self.amount}\n"
            "────────────"
        )
        await log.send(embed=log_embed)

        await self.ticket_channel.delete()

    @discord.ui.button(label="Deny Loan", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if BANK_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("You are not bank staff.", ephemeral=True)

        embed = modern_embed("Loan Denied")
        embed.description = (
            "────────────\n"
            f"Loan denied for <@{self.user_id}>.\n"
            "────────────"
        )
        await interaction.response.edit_message(embed=embed, view=None)

        log = interaction.client.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("LOAN DENIED (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"Bank Staff: {interaction.user.mention}\n"
            f"User: <@{self.user_id}>\n"
            f"Amount Denied: ${self.amount}\n"
            "────────────"
        )
        await log.send(embed=log_embed)

        await self.ticket_channel.delete()


# ============================================================
# MAIN COG
# ============================================================

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.salary_task.start()

    # -----------------------------------------------------------
    # Salary System
    # -----------------------------------------------------------

    @tasks.loop(minutes=1)
    async def salary_task(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                # Role requirement
                if SALARY_ROLE not in [r.id for r in member.roles]:
                    continue

                # Callsign required
                if not member.nick or not re.search(CALLSIGN_REGEX, member.nick):
                    continue

                # VC requirement
                if not member.voice:
                    continue
                if not member.voice.channel:
                    continue
                if not member.voice.channel.category:
                    continue
                if member.voice.channel.category.id != SALARY_VC_CATEGORY:
                    continue

                data = load_data()
                uid = str(member.id)

                if uid not in data["users"]:
                    data["users"][uid] = {"cash": 0, "bank": 0, "debt": 0}

                data["users"][uid]["cash"] += SALARY_AMOUNT
                save_data(data)

                log = self.bot.get_channel(LOG_CHANNEL)
                log_embed = modern_embed("SALARY PAYMENT (AUTO-LOG)")
                log_embed.description = (
                    "────────────\n"
                    f"User: {member.mention}\n"
                    f"Amount: ${SALARY_AMOUNT}\n"
                    "────────────"
                )
                await log.send(embed=log_embed)

    @salary_task.before_loop
    async def before_salary(self):
        await self.bot.wait_until_ready()

    # -----------------------------------------------------------
    # /balance
    # -----------------------------------------------------------

    @app_commands.command(name="balance", description="Check your balance")
    async def balance(self, interaction: discord.Interaction):
        data = load_data()
        uid = str(interaction.user.id)

        if uid not in data["users"]:
            data["users"][uid] = {"cash": 0, "bank": 0, "debt": 0}
            save_data(data)

        bal = data["users"][uid]

        embed = modern_embed("Your Balance")
        embed.description = (
            "────────────\n"
            f"**Cash:** ${bal['cash']}\n"
            f"**Bank:** ${bal['bank']}\n"
            f"**Debt:** ${bal['debt']}\n"
            "────────────"
        )
        await interaction.response.send_message(embed=embed)

    # -----------------------------------------------------------
    # /gamble
    # -----------------------------------------------------------

    @app_commands.command(name="gamble", description="Gamble your money")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Invalid amount.", ephemeral=True)

        data = load_data()
        uid = str(interaction.user.id)

        if uid not in data["users"]:
            data["users"][uid] = {"cash": 0, "bank": 0, "debt": 0}

        if data["users"][uid]["cash"] < amount:
            return await interaction.response.send_message("Not enough cash.", ephemeral=True)

        # 80% chance to lose
        win = random.random() > 0.8

        if win:
            data["users"][uid]["cash"] += amount
            outcome = f"You won ${amount}!"
        else:
            data["users"][uid]["cash"] -= amount
            outcome = f"You lost ${amount}."

        save_data(data)

        embed = modern_embed("Gamble Results")
        embed.description = (
            "────────────\n"
            f"{outcome}\n"
            "────────────"
        )
        await interaction.response.send_message(embed=embed)

        # Log
        log = self.bot.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("GAMBLE RESULT (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"User: {interaction.user.mention}\n"
            f"Amount: ${amount}\n"
            f"Outcome: {'WIN' if win else 'LOSE'}\n"
            "────────────"
        )
        await log.send(embed=log_embed)

    # -----------------------------------------------------------
    # /pay
    # -----------------------------------------------------------

    @app_commands.command(name="pay", description="Request to pay someone")
    async def pay(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Invalid amount.", ephemeral=True)

        data = load_data()
        uid = str(interaction.user.id)
        tid = str(target.id)

        if uid not in data["users"]:
            data["users"][uid] = {"cash": 0, "bank": 0, "debt": 0}

        if tid not in data["users"]:
            data["users"][tid] = {"cash": 0, "bank": 0, "debt": 0}

        if data["users"][uid]["cash"] < amount:
            return await interaction.response.send_message("You do not have enough money.", ephemeral=True)

        # Create request embed
        embed = modern_embed("New Payment Request")
        embed.description = (
            "────────────\n"
            f"**From:** {interaction.user.mention}\n"
            f"**To:** {target.mention}\n"
            f"**Amount:** ${amount}\n"
            "────────────\n"
            f"<@&{PAY_STAFF_ROLE}> Please review."
        )

        approval_channel = self.bot.get_channel(PAY_APPROVAL_CHANNEL)
        await approval_channel.send(embed=embed, view=PayApprovalView(self.bot, interaction.user.id, target.id, amount))

        await interaction.response.send_message("Your request has been submitted for approval.", ephemeral=True)

        # Log
        log = self.bot.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("PAY REQUEST SUBMITTED (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"From: {interaction.user.mention}\n"
            f"To: {target.mention}\n"
            f"Amount: ${amount}\n"
            "────────────"
        )
        await log.send(embed=log_embed)

    # -----------------------------------------------------------
    # /loan
    # -----------------------------------------------------------

    @app_commands.command(name="loan", description="Request a loan from the bank")
    async def loan(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Invalid amount.", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(BANK_TICKET_CATEGORY)

        # Create ticket channel
        ticket = await guild.create_text_channel(
            name=f"loan-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.get_role(BANK_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )

        embed = modern_embed("Loan Request")
        embed.description = (
            "────────────\n"
            f"User: {interaction.user.mention}\n"
            f"Amount Requested: ${amount}\n"
            "────────────\n"
            f"<@&{BANK_ROLE}> Please review this request."
        )

        await ticket.send(embed=embed, view=LoanApprovalView(self.bot, interaction.user.id, amount, ticket))

        await interaction.response.send_message("Your loan ticket has been created.", ephemeral=True)

        # Log
        log = self.bot.get_channel(LOG_CHANNEL)
        log_embed = modern_embed("LOAN REQUEST SUBMITTED (AUTO-LOG)")
        log_embed.description = (
            "────────────\n"
            f"User: {interaction.user.mention}\n"
            f"Amount: ${amount}\n"
            "────────────"
        )
        await log.send(embed=log_embed)


# ============================================================
# COG SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(Economy(bot))
