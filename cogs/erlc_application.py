# ============================================================
# ERLC WHITELIST APPLICATION SYSTEM (REFINED VERSION)
# ============================================================

from __future__ import annotations
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiosqlite
import discord
from discord.ext import commands

# Configuration
from config import GUILD_ID, STAFF_CHANNEL_ID

# ============================================================
# 🔧 BRANDING & CONFIG
# ============================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "applications.db")
APPLICATION_TITLE = "Lakeview City Roleplay - Whitelisted"
EMBED_COLOR = discord.Color.from_str("#757575")
STAFF_PING_ID = 1328939648621346848

# IDs
PRIVATE_LOG_ID = 1451391006774661222
PUBLIC_RESULT_ID = 1439041854086582282
PASSED_ROLE_ID = 1436150196873461850

# Overrides
OVERRIDE_USER_ID = 934850555728252978

# Assets
ARROW_EMOJI = "<a:Arrow:1339635107580874853>"
ACCEPT_EMOJI = discord.PartialEmoji(name="tickgreen", id=1345474741112275146, animated=True)
DENY_EMOJI = discord.PartialEmoji(name="tickred", id=1345474756132081707, animated=True)
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1377401295220117746/1437245076945375393/WHITELISTED_NO_BACKGROUND.png"
DETAILS_IMAGE_URL = "https://media.discordapp.net/attachments/1363547579324829788/1454619668793790504/WL_1.png?ex=6951bfa2&is=69506e22&hm=25713388ec905f35a037d4b7c3ea221c165e05d2e58677a3640dad2ae1709fd8&animated=true"

FOOTER_TEXT = "LKVC - Whitelisted Automated Services"

# Text Blocks
INTRO_TEXT = (
    "> Welcome to our fully automated entry application system, we have 9 questions that require answering via direct-message. "
    "Once all 9 questions are completed & you submit your application, members of our moderation team will review it within 24 hours.\n\n"
    "> PS: Each question has a 5 minute time limit, to go back, simply type `back`, to cancel; type `cancel`. \n\n"
)

APPLY_DESCRIPTION = (
    "> Welcome to our Whitelisted Entry Application, completing this will allow you to progress & join our whitelisted server. Whitelisted provides a much more enhanced, professional & structured roleplay experience with unlimited opportunities. For more information regarding the whitelisted server, check out the [Whitelisted Guide](https://docs.google.com/document/d/1_VPdefph2lC7MyXdHyjOu5g3O1TqVR0WTo_Zbq04Dds/edit?usp=sharing).\n\n"
    "**``Entry Application Requirements:``**\n"
    "> **``-``** Must be the age of thirteen (13) or above\n"
    "> **``-``** Must not have an excessive amount of moderations within our main server\n"
    "> **``-``** Must be able to access Sonoran CAD, Discord & In-Game at the same time\n"
    "> **``-``** Must have a working microphone\n"
    "> **``-``** Required to be on a PC/Computer\n"
    "> **``-``** Intends on roleplaying according to our whitelisted standards\n\n"
    "**``Whitelisted Department Opportunities:``**\n"
    "> **``-``** <:DPS:1451326688628703302> Department of Public Safety\n"
    "> **``-``** <:LCFR:1451326717942566992> Lakeview City Fire & Rescue\n"
    "> **``-``** <:DOC:1451326657368424581> Department of Communications\n"
    "> **``-``** <:CBA:1451327226179223562> Civilian Business Association\n"
    "> **``-``** <:Factions:1451327473907273764> Faction Operations\n"
    "> **``-``** <:Courts:1455076019823317053> Lakeview City Courts\n"
    "> **``-``** <:DMV2:1455075715887272049> Department of Motor Vehicles"
)

QUESTIONS = [
    "Why do you want to join our whitelisted server?", "How old are you?", "What timezone are you in?",
    "How did you find our [main server](https://discord.gg/lkvc)?", "A customer refuses to pay for an item in a business you own. How do you respond to this?",
    "How would you handle a vehicle pursuit continuing behind you down Riverside Drive?", "You are being pulled over by a Law Enforcement Officer, how do you make this traffic stop more entertaining?",
    "As you are driving home, you see a homeless person sat on your front door. What do you do?",
    "A driver crashes behind you. What steps do you take?"
]

# ============================================================
# 🗄 DATABASE & HELPERS
# ============================================================

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS applications (case_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, status TEXT, submitted_at TEXT, staff_id INTEGER, reason TEXT, cooldown_until TEXT);
            CREATE TABLE IF NOT EXISTS answers (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, question TEXT, answer TEXT);
            CREATE TABLE IF NOT EXISTS blacklists (user_id INTEGER PRIMARY KEY, staff_id INTEGER, reason TEXT, timestamp TEXT);
        """)
        try:
            await db.execute("ALTER TABLE applications ADD COLUMN cooldown_until TEXT");
            await db.commit()
        except:
            pass

def get_footer_data(bot: commands.Bot):
    guild = bot.get_guild(GUILD_ID)
    icon = guild.icon.url if guild and guild.icon else None
    return icon

# ============================================================
# 🔘 UI CLASSES
# ============================================================

class BlacklistConfirm(discord.ui.View):
    def __init__(self, review_view, user_id: int):
        super().__init__(timeout=30)
        self.review_view, self.user_id = review_view, user_id

    @discord.ui.button(label="Confirm Permanent Blacklist", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO blacklists (user_id, staff_id, reason, timestamp) VALUES (?, ?, ?, ?)",
                (self.user_id, interaction.user.id, "Blacklisted via Review", datetime.now().isoformat()))
            await db.commit()
        await interaction.response.edit_message(content="User has been blacklisted.", view=None)
        await self.review_view._archive(interaction, "blacklisted", "Permanent server blacklist.", 9999)

class CooldownPicker(discord.ui.View):
    def __init__(self, review_view, interaction: discord.Interaction, reason: str):
        super().__init__(timeout=60)
        self.review_view, self.staff_itn, self.reason = review_view, interaction, reason

    @discord.ui.select(
        placeholder="Select Cooldown Duration",
        options=[
            discord.SelectOption(label="No Cooldown", value="0"),
            discord.SelectOption(label="3 Days", value="3"),
            discord.SelectOption(label="7 Days", value="7"),
            discord.SelectOption(label="14 Days", value="14"),
            discord.SelectOption(label="30 Days", value="30"),
        ]
    )
    async def select_cd(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        await self.review_view._archive(self.staff_itn, "denied", self.reason, int(select.values[0]))

class DenialReasonModal(discord.ui.Modal, title="Application Denial"):
    reason = discord.ui.TextInput(label="Reason for Denial", style=discord.TextStyle.paragraph, required=True, min_length=5)

    def __init__(self, review_view):
        super().__init__()
        self.review_view = review_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Select a cooldown duration:",
                                                view=CooldownPicker(self.review_view, interaction, self.reason.value),
                                                ephemeral=True)

class ReviewView(discord.ui.View):
    def __init__(self, cog, case_id: int, user_id: int, answers: list, stats: tuple):
        super().__init__(timeout=None)
        self.cog, self.case_id, self.user_id, self.answers, self.stats = cog, case_id, user_id, answers, stats
        self.current_page = 0

    def create_embed(self):
        icon = get_footer_data(self.cog.bot)
        q, a = self.answers[self.current_page]
        e = discord.Embed(title=f"Whitelist Review • Case #{self.case_id}", color=EMBED_COLOR)
        e.set_thumbnail(url=THUMBNAIL_URL)
        e.add_field(name="Applicant", value=f"<@{self.user_id}> (`{self.user_id}`)", inline=True)
        e.add_field(name="Stats", value=f"{ACCEPT_EMOJI} {self.stats[1]} | {DENY_EMOJI} {self.stats[2]}", inline=True)
        e.add_field(name=f"Question {self.current_page + 1}/9", value=f"**{q}**\n```\n{a}\n```", inline=False)
        e.set_footer(text=FOOTER_TEXT, icon_url=icon)
        return e

    async def _archive(self, interaction: discord.Interaction, status: str, reason: str, cooldown_days: int = 0):
        cd_ts = (datetime.now() + timedelta(days=cooldown_days)).isoformat() if cooldown_days > 0 else None
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE applications SET status=?, staff_id=?, reason=?, cooldown_until=? WHERE case_id=?",
                             (status, interaction.user.id, reason, cd_ts, self.case_id))
            await db.commit()

        if interaction.message: await interaction.message.delete()
        icon = get_footer_data(self.cog.bot)

        # 1. Private Detail Log
        pl = self.cog.bot.get_channel(PRIVATE_LOG_ID)
        if pl:
            # Using your requested #757575 color for consistency
            le = discord.Embed(
                title=f"Application Review Log | Case #{self.case_id}",
                color=discord.Color.from_str("#757575"),
                timestamp=datetime.now()
            )

            le.set_thumbnail(url=THUMBNAIL_URL)

            # Organizing metadata into fields for better scannability
            le.add_field(name="Staff Member", value=f"{interaction.user.mention}\n(`{interaction.user.id}`)",
                         inline=True)
            le.add_field(name="Applicant", value=f"<@{self.user_id}>\n(`{self.user_id}`)", inline=True)
            le.add_field(name="Verdict", value=f"**{status.upper()}**", inline=True)

            le.add_field(name="Reason/Staff Note", value=f"```\n{reason}\n```", inline=False)

            # Formatting the transcript with numbered bullets for a cleaner look
            transcript_text = ""
            for i, (q, a) in enumerate(self.answers, 1):
                transcript_text += f"[{i}] {q}\n> {a}\n\n"

            # Ensure transcript doesn't exceed Discord's 1024 field limit
            if len(transcript_text) > 1000:
                transcript_text = transcript_text[:997] + "..."

            le.add_field(name="Application Transcript", value=f"```\n{transcript_text}```", inline=False)

            le.set_footer(text=f"{FOOTER_TEXT} • Case Review System", icon_url=icon)
            await pl.send(embed=le)

            # 2. Public Results
            public_msg = None
            pr = self.cog.bot.get_channel(PUBLIC_RESULT_ID)
            if pr:
                # Fixed the brackets and moved thumbnail outside the constructor
                pe = discord.Embed(
                    title="Whitelisted Entry Level Application: Public Result",
                    color=discord.Color.from_str("#757575")
                )
                pe.set_thumbnail(url=THUMBNAIL_URL)

                if status == "approved":
                    pe.description = (
                        f"> Congratulations, <@{self.user_id}>! Your entry level application was reviewed by our Staff Team & was deemed fitting to join whitelisted! "
                        f" To continue - you need to join our Sonoran CAD, check this out [here](https://discord.com/channels/1328475009542258688/1439048210801885265).\n\n"
                        f"> **Applicant:** <@{self.user_id}>, ({self.user_id}).\n"
                        f"> **Result:** Accepted\n"
                        f"> **Application Number:** {self.case_id}"
                    )
                else:
                    pe.description = (
                        f"> Hello <@{self.user_id}>, thank you for showing an interest into our Whitelisted Server, however your application has been denied - you were sent additional information via Direct-Messages.\n\n"
                        f"> **Applicant:** <@{self.user_id}>, ({self.user_id}).\n"
                        f"> **Result:** Denied\n"
                        f"> **Reason:** {reason}.\n"
                        f"> **Application Number:** {self.case_id}"
                    )


                pe.set_footer(text=FOOTER_TEXT, icon_url=icon)
                public_msg = await pr.send(content=f"<@{self.user_id}>", embed=pe)

                # 3. User DM Embed
                m = interaction.guild.get_member(self.user_id)
                if m:
                    try:
                        if status == "approved":
                            # Added missing ) at the end of the line
                            de = discord.Embed(title="Whitelisted Entry Application: Passed!",
                                               color=discord.Color.from_str("#757575"))
                            de.description = (
                                f"> Congratulations, <@{self.user_id}> on completing & passing our entry level application, simply complete the Sonoran CAD Sign-up & the provisional license creation to continue within the server, for additional information review https://discord.com/channels/1328475009542258688/1439048050713563267\n\n"
                                f"Your roles were automatically updated, contact our team if you require assistance."
                            )
                        else:
                            # Added missing ) at the end of the line
                            de = discord.Embed(title="Whitelisted Entry Application: Update",
                                               color=discord.Color.from_str("#757575"))
                            # Fixed missing closing quote and parenthesis
                            de.description = (
                                f"> Thank you for expressing an interest into our whitelisted server, unfortunately - you have failed the entry level application. We have added these notes: **{reason}**."
                            )
                            if cooldown_days > 0:
                                de.description += f"\n\nYou are eligible to re-apply in **{cooldown_days} days**."

                        if public_msg:
                            de.description += f"\n\n[**Jump to additional information:**]({public_msg.jump_url})"

                        de.set_thumbnail(url=THUMBNAIL_URL)
                        de.set_footer(text=FOOTER_TEXT, icon_url=icon)
                        # Added the requested image URL at the bottom
                        de.set_image(
                            url="https://cdn.discordapp.com/attachments/1323165604215132273/1332115964774580296/image.png?ex=6945d2ab&is=6944812b&hm=3f4693b48ada5c2353a4eea5d94d973487a2d70f951eff2faf75bc46fec2d6d8&")
                        await m.send(content=f"<@{self.user_id}>", embed=de)
                    except Exception as e:
                        print(f"Failed to DM user: {e}")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray)
    async def prev(self, itn, _):
        if self.current_page > 0:
            self.current_page -= 1
            await itn.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, itn, _):
        if self.current_page < len(self.answers) - 1:
            self.current_page += 1
            await itn.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.secondary, emoji=ACCEPT_EMOJI)
    async def accept(self, itn, _):
        m = itn.guild.get_member(self.user_id)
        if m:
            r = itn.guild.get_role(PASSED_ROLE_ID)
            if r: await m.add_roles(r)
        await itn.response.defer()
        await self._archive(itn, "approved", "Requirements Met.")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.secondary, emoji=DENY_EMOJI)
    async def deny(self, itn, _):
        await itn.response.send_modal(DenialReasonModal(self))

    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.danger)
    async def blacklist(self, itn, _):
        await itn.response.send_message("Are you sure you want to blacklist this user?",
                                        view=BlacklistConfirm(self, self.user_id), ephemeral=True)

class StartView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Start Application", style=discord.ButtonStyle.secondary, emoji=ARROW_EMOJI,
                       custom_id="lkvc_start_final")
    async def start(self, interaction: discord.Interaction, _):
        try:
            await self.cog.start_application(interaction.user)
            await interaction.response.send_message("📨 Check your Direct Messages!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I cannot Drect-Message you. Please open your DMs via settings.", ephemeral=True)

class ERLCWhitelistApplication(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions = {}

    async def cog_load(self):
        await init_db()
        self.bot.add_view(StartView(self))

    async def start_application(self, user: discord.Member):
        # BYPASS ALL CHECKS FOR OVERRIDE USER
        if user.id != OVERRIDE_USER_ID:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT 1 FROM blacklists WHERE user_id = ?", (user.id,)) as c:
                    if await c.fetchone(): return await user.send("❌ You are blacklisted.")
                async with db.execute(
                        "SELECT status, cooldown_until FROM applications WHERE user_id = ? ORDER BY case_id DESC LIMIT 1",
                        (user.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        if row[0] == 'pending': return await user.send("Already pending.")
                        if row[1] and datetime.now() < datetime.fromisoformat(row[1]):
                            return await user.send(f"You are on cooldown until {row[1]}.")

        icon = get_footer_data(self.bot)
        e = discord.Embed(title=APPLICATION_TITLE, description=INTRO_TEXT, color=EMBED_COLOR)
        e.set_image(url=DETAILS_IMAGE_URL)
        e.set_thumbnail(url=THUMBNAIL_URL)
        e.set_footer(text=FOOTER_TEXT, icon_url=icon)

        view = discord.ui.View()
        btn = discord.ui.Button(label="Begin Application", style=discord.ButtonStyle.secondary, emoji=ARROW_EMOJI)

        async def cb(itn):
            await itn.response.defer()
            await itn.delete_original_response()
            await self.run_questions(user)

        btn.callback = cb
        view.add_item(btn)
        await user.send(embed=e, view=view)

    async def run_questions(self, user: discord.Member):
        dm = user.dm_channel or await user.create_dm()
        self.sessions[user.id] = []
        icon = get_footer_data(self.bot)
        idx = 0
        while idx < len(QUESTIONS):
            q = QUESTIONS[idx]
            bar = "▰" * (idx + 1) + "▱" * (len(QUESTIONS) - (idx + 1))

            e = discord.Embed(title=f"Progress Bar: {bar}",
                              description=f"** {ARROW_EMOJI} Question {idx + 1}/9:** {q}\n\n", color=EMBED_COLOR)
            e.set_footer(text="Type back to go back, or cancel to stop!", icon_url=icon)

            await dm.send(embed=e)
            try:
                m = await self.bot.wait_for("message", timeout=300,
                                            check=lambda m: m.author.id == user.id and isinstance(m.channel,
                                                                                                  discord.DMChannel))
                content = m.content.strip()
                if content.lower() == "cancel":
                    self.sessions.pop(user.id, None)
                    return await dm.send(" **Application Cancelled.**")
                if content.lower() == "back":
                    if idx > 0:
                        idx -= 1
                        self.sessions[user.id].pop()
                        continue
                    else:
                        await dm.send(" **This is the first question!**")
                        continue
                self.sessions[user.id].append(content)
                idx += 1
            except asyncio.TimeoutError:
                self.sessions.pop(user.id, None)
                return await dm.send("**Timed Expired**! Please restart the application.")
        await self.finalize(user)

    async def finalize(self, user: discord.Member):
        ans = self.sessions.pop(user.id)
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "INSERT INTO applications (user_id, status, submitted_at) VALUES (?, 'pending', datetime('now'))",
                (user.id,))
            case_id = cur.lastrowid
            for q, a in zip(QUESTIONS, ans):
                await db.execute("INSERT INTO answers (case_id, question, answer) VALUES (?, ?, ?)", (case_id, q, a))
            await db.commit()
            async with db.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END), SUM(CASE WHEN status='denied' THEN 1 ELSE 0 END) FROM applications WHERE user_id=?",
                    (user.id,)) as c:
                stats = await c.fetchone()
        await user.send(
            f"{ACCEPT_EMOJI} **Your application was submitted**, please allow up to 24 hours for it to be reviewed.")
        chan = self.bot.get_channel(STAFF_CHANNEL_ID)
        if chan:
            view = ReviewView(self, case_id, user.id, list(zip(QUESTIONS, ans)), stats)
            await chan.send(content=f"<@&{STAFF_PING_ID}>", embed=view.create_embed(), view=view)

    @commands.command(name="apply")
    async def apply_cmd(self, ctx):
        if ctx.guild and ctx.guild.id == GUILD_ID:
            icon = get_footer_data(self.bot)
            e = discord.Embed(title=APPLICATION_TITLE, description=APPLY_DESCRIPTION, color=EMBED_COLOR)
            e.set_image(url=DETAILS_IMAGE_URL)
            e.set_thumbnail(url=THUMBNAIL_URL)
            e.set_footer(text=FOOTER_TEXT, icon_url=icon)
            await ctx.send(embed=e, view=StartView(self))

    # ============================================================
    # 🛡 STAFF COMMANDS
    # ============================================================

    @commands.command(name="unblacklist")
    @commands.has_role(1328939648621346848)
    async def unblacklist_cmd(self, ctx, user: discord.User):
        """Removes blacklist, clears cooldowns, and allows immediate re-application."""
        if ctx.guild and ctx.guild.id != GUILD_ID:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            # 1. Delete from the blacklist table
            await db.execute("DELETE FROM blacklists WHERE user_id = ?", (user.id,))

            # 2. Reset the status and cooldown in the applications table
            await db.execute(
                "UPDATE applications SET status = 'cleared', cooldown_until = NULL WHERE user_id = ?",
                (user.id,)
            )
            await db.commit()

        # Ephemeral only works for interactions. For commands, we just send it:
        await ctx.send(
            f" **Success:** {user.mention} has been unblacklisted and all cooldowns wiped. They can re-apply now.")

    @unblacklist_cmd.error
    async def unblacklist_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            await ctx.send("You do not have the required staff permissions to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please provide a user to unblacklist. (Usage: `!unblacklist @user` or `ID`)")

async def setup(bot):
    await bot.add_cog(ERLCWhitelistApplication(bot))