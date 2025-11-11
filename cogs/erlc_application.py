# cogs/erlc_application.py
from __future__ import annotations

import os, json, asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

# IDs come from config.py
from config import GUILD_ID, STAFF_CHANNEL_ID, APPROVED_ROLE_ID

APPLICATIONS_JSON_PATH = "applications.json"
PER_USER_COOLDOWN_MINUTES = 30
PER_QUESTION_TIMEOUT_SECS = 180

EMBED_COLOR = discord.Color(int("757575", 16))
THUMBNAIL_URL = "https://media.discordapp.net/attachments/1377401295220117746/1437245076945375393/WHITELISTED_NO_BACKGROUND.png?ex=69128a49&is=691138c9&hm=7ed279a4590e9d588636106385fd172766e685e38f90655d4363298706f3c5ab&=&format=png&quality=lossless"
FOOTER_ICON_URL = "https://media.discordapp.net/attachments/1437239908237447290/1437240720292315186/image.png?ex=6912863a&is=691134ba&hm=686a2fcc1859a6f4251e3a49eb07fe3dd80bd085e86c442d55ade9079475bc98&=&format=png&quality=lossless"
FOOTER_TEXT = "Whitelisted Automated Services"
ANSWER_REACT_EMOJI_ID = 1345474741112275146

QUESTIONS: List[str] = [
    "Why do you want to join whitelisted?",
    "What is your age?",
    "What timezone are you in?",
    "How did you find our main server?",
    "Your character is running a business, but a customer refuses to pay for services. How do you roleplay the situation?",
    "You are involved in a car accident in-game. What steps do you take to handle the situation realistically?",
    "Your character is being pulled over by Law Enforcement Officers, how could you make a regular traffic stop more enjoyable & realistic?",
    "You arrive back to your house to find that a homeless person is outside, how do you handle this?",
    "A driver behind you crashes, what are the steps you would take to safely help them?",
]

INSTRUCTIONS = (
    "I’ll DM you the whitelist application questions now.\n\n"
    "Type `cancel` at any time to stop, or `back` to re-answer the previous question.\n"
    f"You’ll have **{PER_QUESTION_TIMEOUT_SECS // 60} minutes per question**."
)

_file_lock = asyncio.Lock()


async def _load_all() -> Dict[str, Any]:
    if not os.path.exists(APPLICATIONS_JSON_PATH):
        return {"last_case": 0, "applications": []}
    async with _file_lock:
        return await asyncio.to_thread(_read_json, APPLICATIONS_JSON_PATH)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _save_all(payload: Dict[str, Any]) -> None:
    async with _file_lock:
        await asyncio.to_thread(_write_json, APPLICATIONS_JSON_PATH, payload)


def _write_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now_hr() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass
class ApplicationSession:
    user_id: int
    guild_id: int
    current_index: int = 0
    answers: List[str] = field(default_factory=list)
    started_at: str = field(default_factory=_now_hr)


class ApplicationActionView(discord.ui.View):
    def __init__(self, case_id: int, applicant_id: int, guild_id: int):
        super().__init__(timeout=1800)  # Optional timeout
        self.case_id = case_id
        self.applicant_id = applicant_id
        self.guild_id = guild_id

    async def _get_member(self, interaction: discord.Interaction) -> Optional[discord.Member]:
        guild = interaction.client.get_guild(self.guild_id) or await interaction.client.fetch_guild(self.guild_id)
        try:
            return guild.get_member(self.applicant_id) or await guild.fetch_member(self.applicant_id)
        except Exception:
            return None

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button):
        notes = []
        member = await self._get_member(interaction)
        if member and APPROVED_ROLE_ID:
            role = member.guild.get_role(APPROVED_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role, reason=f"Whitelist approved (Case {self.case_id})")
                    notes.append(f"Gave role **{role.name}**.")
                except discord.Forbidden:
                    notes.append("Missing permission to add role.")
        try:
            user = await interaction.client.fetch_user(self.applicant_id)
            emb = discord.Embed(
                title=f"Application Approved • Case #{self.case_id}",
                description="🎉 Your ERLC whitelist application has been **approved**. Welcome!",
                color=EMBED_COLOR, timestamp=datetime.now(timezone.utc),
            )
            emb.set_thumbnail(url=THUMBNAIL_URL)
            emb.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
            await user.send(embed=emb);
            dm_note = "(DM sent.)"
        except Exception:
            dm_note = "(Could not DM applicant.)"
        note_str = " ".join(notes) if notes else "No extra actions."
        await interaction.response.send_message(f"✅ **Approved** Case #{self.case_id}. {note_str} {dm_note}",
                                                ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="⛔")
    async def deny(self, interaction: discord.Interaction, _: discord.ui.Button):
        try:
            user = await interaction.client.fetch_user(self.applicant_id)
            emb = discord.Embed(
                title=f"Application Denied • Case #{self.case_id}",
                description="❌ Your ERLC whitelist application has been **denied**. You may reapply later.",
                color=EMBED_COLOR, timestamp=datetime.now(timezone.utc),
            )
            emb.set_thumbnail(url=THUMBNAIL_URL)
            emb.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
            await user.send(embed=emb);
            dm_note = "(DM sent.)"
        except Exception:
            dm_note = "(Could not DM applicant.)"
        await interaction.response.send_message(f"⛔ **Denied** Case #{self.case_id}. {dm_note}", ephemeral=True)

    # REMOVED: The 'Ask Follow-up' button code block is removed as requested.
    # The view now only contains Approve and Deny buttons.


class StartApplicationView(discord.ui.View):
    def __init__(self, parent_cog: "ERLCWhitelistApplication"):
        super().__init__(timeout=None)
        self.parent_cog = parent_cog

    @discord.ui.button(label="Start Application", style=discord.ButtonStyle.gray, emoji="📝",
                       custom_id="erlc_start_whitelist_app")
    async def start(self, interaction: discord.Interaction, _: discord.ui.Button):
        cd_msg = await self.parent_cog._can_start(interaction.user.id)
        if cd_msg: return await interaction.response.send_message(cd_msg, ephemeral=True)
        await interaction.response.send_message("Check your DMs to begin your whitelist application.", ephemeral=True)
        await self.parent_cog._run_questionnaire(interaction, interaction.user)


class ERLCWhitelistApplication(commands.Cog):
    """Prefix-only ?apply -> channel embed with button -> DM questionnaire."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[int, ApplicationSession] = {}
        self.cooldowns: Dict[int, float] = {}
        self.session_lock = asyncio.Lock()
        self.bot.add_view(StartApplicationView(self))

    async def _can_start(self, user_id: int) -> Optional[str]:
        now = asyncio.get_event_loop().time()
        wait_left = self.cooldowns.get(user_id, 0.0) - now
        if wait_left > 0:
            return f"Please wait **{int(wait_left // 60)}m {int(wait_left % 60)}s** before starting another application."
        return None

    def _set_cooldown(self, user_id: int):
        self.cooldowns[user_id] = asyncio.get_event_loop().time() + PER_USER_COOLDOWN_MINUTES * 60

    async def _persist_application(self, applicant: discord.abc.User, answers: List[str]) -> int:
        data = await _load_all()
        data["last_case"] = int(data.get("last_case", 0)) + 1
        case_id = data["last_case"]
        data.setdefault("applications", []).append({
            "case_id": case_id, "applicant_id": applicant.id, "applicant_tag": str(applicant),
            "submitted_at": _now_hr(), "answers": answers, "questions": QUESTIONS,
        })
        await _save_all(data)
        return case_id

    async def _post_to_staff(self, case_id: int, member: discord.abc.User, answers: List[str]) -> Optional[
        discord.Message]:
        try:
            # FIX: Use fetch_channel for reliable channel retrieval
            ch = await self.bot.fetch_channel(STAFF_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden):
            # If the channel is not found or forbidden, log it and return None
            print(f"ERROR: Could not fetch staff channel {STAFF_CHANNEL_ID}. Check ID/Permissions.")
            return None

        if not isinstance(ch, (discord.TextChannel, discord.Thread)): return None

        emb = discord.Embed(title=f"ERLC Whitelist Application • Case #{case_id}", color=EMBED_COLOR,
                            timestamp=datetime.now(timezone.utc))
        emb.set_thumbnail(url=THUMBNAIL_URL)
        emb.add_field(name="Applicant", value=f"{member.mention} (`{member}` / `{member.id}`)", inline=False)
        emb.add_field(name="Case Counter", value=f"**#{case_id}**", inline=True)
        emb.add_field(name="Submitted", value=_now_hr(), inline=True)

        # CONFIRMED: This loop correctly adds all Q/A pairs to the embed fields.
        for i, (q, a) in enumerate(zip(QUESTIONS, answers), start=1):
            emb.add_field(name=f"Q{i}. {q}",
                          value=(a if len(a) <= 1024 else a[:1000] + " …(truncated)") or "*No answer*", inline=False)

        emb.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)

        view = ApplicationActionView(case_id=case_id, applicant_id=member.id, guild_id=GUILD_ID)
        msg = await ch.send(embed=emb, view=view)

        # Thread creation logic (unchanged)
        try:
            if isinstance(ch, discord.TextChannel):
                th = await ch.create_thread(
                    name=f"App • Case #{case_id} • {getattr(member, 'display_name', 'Applicant')}",
                    type=discord.ChannelType.private_thread, auto_archive_duration=1440)
                await th.send(f"Private staff thread for Case **#{case_id}** — Applicant: {member.mention}")
        except Exception:
            pass
        return msg

    async def _run_questionnaire(self, ctx_or_inter: Any, user: discord.User) -> None:
        try:
            dm = await user.create_dm()
            intro = discord.Embed(title="Whitelist Application — ERLC", description=INSTRUCTIONS,
                                  color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
            intro.set_thumbnail(url=THUMBNAIL_URL)
            intro.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
            await dm.send(embed=intro)
        except discord.Forbidden:
            if hasattr(ctx_or_inter, "response") and not ctx_or_inter.response.is_done():
                return await ctx_or_inter.response.send_message("I can’t DM you. Enable DMs and try again.",
                                                                ephemeral=True)
            return

        async with self.session_lock:
            sess = self.sessions.get(user.id) or ApplicationSession(user_id=user.id, guild_id=GUILD_ID)
            self.sessions[user.id] = sess

        while sess.current_index < len(QUESTIONS):
            q = QUESTIONS[sess.current_index]
            await dm.send(f"**Q{sess.current_index + 1}/{len(QUESTIONS)}** — {q}\n"
                          "_Reply with your answer. (`back` to go to previous, `cancel` to stop)_")

            def check(m: discord.Message):
                return m.author.id == user.id and m.channel.id == dm.id

            try:
                msg: discord.Message = await self.bot.wait_for("message", check=check,
                                                               timeout=PER_QUESTION_TIMEOUT_SECS)
            except asyncio.TimeoutError:
                timeout = discord.Embed(title="Application Timed Out",
                                        description="⏰ You can run `?apply` again to restart.",
                                        color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
                timeout.set_thumbnail(url=THUMBNAIL_URL);
                timeout.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
                await dm.send(embed=timeout)
                async with self.session_lock:
                    self.sessions.pop(user.id, None)
                return

            content = msg.content.strip().lower()
            if content == "cancel":
                cancel = discord.Embed(title="Application Cancelled",
                                       description="❌ You can start again anytime with `?apply`.",
                                       color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
                cancel.set_thumbnail(url=THUMBNAIL_URL);
                cancel.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
                await dm.send(embed=cancel)
                async with self.session_lock: self.sessions.pop(user.id, None)
                return
            if content == "back":
                if sess.current_index > 0:
                    sess.current_index -= 1
                    if len(sess.answers) > sess.current_index: sess.answers.pop()
                    await dm.send("↩️ Going back to the previous question.")
                else:
                    await dm.send("You’re already at the first question.")
                try:
                    await msg.add_reaction(discord.PartialEmoji(id=ANSWER_REACT_EMOJI_ID))
                except:
                    pass
                continue

            # save & react
            answer = msg.content.strip()
            if len(sess.answers) == sess.current_index:
                sess.answers.append(answer)
            else:
                sess.answers[sess.current_index] = answer
            try:
                await msg.add_reaction(discord.PartialEmoji(id=ANSWER_REACT_EMOJI_ID))
            except:
                pass
            sess.current_index += 1

        case_id = await self._persist_application(user, sess.answers)
        done = discord.Embed(title=f"Application Submitted • Case #{case_id}",
                             description="✅ Thanks! Your application has been submitted to staff.",
                             color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
        done.set_thumbnail(url=THUMBNAIL_URL)
        done.add_field(name="Case Counter", value=f"**#{case_id}**", inline=True)
        done.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
        await dm.send(embed=done)
        await self._post_to_staff(case_id, user, sess.answers)
        async with self.session_lock:
            self.sessions.pop(user.id, None)
        self._set_cooldown(user.id)

    @commands.command(name="apply")
    async def apply_prefix(self, ctx: commands.Context):
        try:
            if ctx.message and ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await ctx.message.delete()
        except:
            pass
        embed = discord.Embed(title="Whitelist Application",
                              description="Click the button below to start your DM application.\nYou’ll need DMs enabled.",
                              color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=THUMBNAIL_URL)
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON_URL)
        await ctx.send(embed=embed, view=StartApplicationView(self))


# required entrypoint for extensions
async def setup(bot: commands.Bot):
    await bot.add_cog(ERLCWhitelistApplication(bot))