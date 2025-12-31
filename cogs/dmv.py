import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import aiosqlite
import discord
from discord.ext import commands

import gspread
from google.oauth2.service_account import Credentials

# =========================
# CONFIG
# =========================

GOOGLE_SA_FILE = "google_service_account.json"
GOOGLE_SHEET_ID = "1cWyhzexhdmblkxFZyGHOlSQ78UDfZ1pwo9Lrc1zMPGQ"
GOOGLE_SHEET_TAB_NAME = "Licenses"  # main tab
GOOGLE_HISTORY_TAB_NAME = "DMV History"  # history tab

SUSPENDED_ROLE_ID = 1454666345357643838
OUTDATED_PING_ROLE_ID = 1454666047054676010
OUTDATED_CHANNEL_ID = 1455637956566974474

DEFAULT_SUSPENSION_THRESHOLD = 16

# How many history rows to show in Discord at once
HISTORY_PAGE_SIZE = 5
HISTORY_MAX_FETCH = 25

log = logging.getLogger("dmv")


@dataclass
class LicenseInfo:
    roblox_username: str = ""
    roblox_display: str = ""
    roleplay_name: str = ""
    age: Optional[int] = None
    address: str = ""
    eye_color: str = ""
    height: str = ""
    license_number: str = ""
    license_type: str = ""
    license_code: str = ""
    issued_at: str = ""
    expires_at: str = ""


# =========================
# UI: Pagination for /dmv history
# =========================

class HistoryView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        member: discord.abc.User,
        rows: List[Tuple[str, str, int, str, str]],
        page_size: int = HISTORY_PAGE_SIZE,
        timeout: int = 120,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.member = member
        self.rows = rows
        self.page_size = page_size
        self.page = 0

        # Disable buttons appropriately at start
        self._sync_buttons()

    def _sync_buttons(self):
        max_page = max(0, (len(self.rows) - 1) // self.page_size)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "prev":
                    child.disabled = self.page <= 0
                elif child.custom_id == "next":
                    child.disabled = self.page >= max_page

    def _make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"DMV History — {self.member}",
            color=discord.Color.blurple(),
        )
        if not self.rows:
            embed.description = "No DMV history found."
            return embed

        start = self.page * self.page_size
        end = start + self.page_size
        chunk = self.rows[start:end]

        lines = []
        for code, title, points, reason, ts in chunk:
            # ts is ISO; make it pretty
            pretty_ts = ts.replace("T", " ").replace("Z", "")
            reason_txt = f" — {reason}" if reason else ""
            title_txt = f" ({title})" if title and title != code else ""
            lines.append(f"• **{code}**{title_txt}: **+{points}** pts — `{pretty_ts}`{reason_txt}")

        embed.description = "\n".join(lines)

        max_page = max(0, (len(self.rows) - 1) // self.page_size)
        embed.set_footer(text=f"Page {self.page + 1}/{max_page + 1} • Showing {min(len(self.rows), HISTORY_MAX_FETCH)} most recent")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the invoker can use the pagination controls
        if interaction.user and interaction.user.id != self.author_id:
            await interaction.response.send_message("These buttons aren’t for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_page = max(0, (len(self.rows) - 1) // self.page_size)
        self.page = min(max_page, self.page + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(view=self)


# =========================
# COG
# =========================

class DMVCog(commands.Cog):
    """
    DMV / Points System (SQLite + Google Sheets)

    DB tables:
      - dmv_records(discord_id, total_points)
      - dmv_history(id, discord_id, code, title, points, reason, timestamp)
      - licenses(discord_id, roblox/license fields)
      - dmv_config(key, value)  -> stores suspension threshold, etc.

    Google Sheets:
      - Updates Licenses tab when points change.
      - Appends to DMV History tab when a citation is logged.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._worksheet = None
        self._history_worksheet = None

        # Prevent race conditions on the same user
        self._locks: Dict[int, asyncio.Lock] = {}

        # In case Sheets isn't ready yet, don't explode
        self._gsheets_ready = asyncio.Event()

    # -------------------------
    # Lifecycle
    # -------------------------

    async def cog_load(self):
        # Ensures bot.db exists from your setup_hook
        await self._ensure_db_tables()
        await self._setup_gsheets_async()
        log.info("[DMV] DMV cog loaded. DB ready; Google Sheets init attempted.")

    def _get_lock(self, discord_id: int) -> asyncio.Lock:
        if discord_id not in self._locks:
            self._locks[discord_id] = asyncio.Lock()
        return self._locks[discord_id]

    # -------------------------
    # Config (threshold)
    # -------------------------

    async def _get_threshold(self) -> int:
        db: aiosqlite.Connection = self.bot.db
        async with db.execute("SELECT value FROM dmv_config WHERE key = 'suspension_threshold'") as cur:
            row = await cur.fetchone()
        if not row:
            return DEFAULT_SUSPENSION_THRESHOLD
        try:
            return int(row[0])
        except Exception:
            return DEFAULT_SUSPENSION_THRESHOLD

        async def _handle_new_suspension(self, member: discord.Member, total_points: int, threshold: int):
            # DM the user
            try:
                embed = discord.Embed(
                    title="🚫 License Suspended",
                    description=(
                        f"Your license is now **SUSPENDED**.\n\n"
                        f"**Total Points:** {total_points}\n"
                        f"**Threshold:** {threshold}"
                    ),
                    color=discord.Color.red(),
                )
                await member.send(embed=embed)
            except Exception:
                pass

            # Add suspended role
            try:
                role = member.guild.get_role(SUSPENDED_ROLE_ID)
                if role and role not in member.roles:
                    await member.add_roles(role, reason="DMV: License suspended (threshold exceeded)")
            except Exception:
                pass

            # Ping outdated role in the channel
            try:
                channel = member.guild.get_channel(OUTDATED_CHANNEL_ID) or self.bot.get_channel(OUTDATED_CHANNEL_ID)
                if channel:
                    await channel.send(
                        f"<@&{OUTDATED_PING_ROLE_ID}> outdated — {member.mention} ({member.id}) is now **SUSPENDED** "
                        f"({total_points}/{threshold} points)."
                    )
            except Exception:
                pass

    async def _set_threshold(self, value: int) -> None:
        db: aiosqlite.Connection = self.bot.db
        await db.execute(
            """
            INSERT INTO dmv_config (key, value)
            VALUES ('suspension_threshold', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(value),),
        )
        await db.commit()

    async def _is_suspended(self, total_points: int) -> bool:
        threshold = await self._get_threshold()
        return total_points >= threshold

    # -------------------------
    # DB init
    # -------------------------

    async def _ensure_db_tables(self):
        db: aiosqlite.Connection = self.bot.db

        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS dmv_records (
                discord_id INTEGER PRIMARY KEY,
                total_points INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS dmv_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                title TEXT,
                points INTEGER NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )

        # License info table (filled when license is created in your other system)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                discord_id INTEGER PRIMARY KEY,
                roblox_username TEXT,
                roblox_display TEXT,
                roleplay_name TEXT,
                age INTEGER,
                address TEXT,
                eye_color TEXT,
                height TEXT,
                license_number TEXT,
                license_type TEXT,
                license_code TEXT,
                issued_at TEXT,
                expires_at TEXT
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS dmv_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        await db.commit()

    # -------------------------
    # Google Sheets init (async wrapper)
    # -------------------------
    async def _setup_gsheets_async(self):
        if not os.path.exists(GOOGLE_SA_FILE):
            log.warning("[DMV] Google service account file not found: %s", GOOGLE_SA_FILE)
            self._gsheets_ready.clear()
            return

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(GOOGLE_SA_FILE, scopes=scopes)

        def _connect_sync():
            client = gspread.authorize(creds)
            sheet = client.open_by_key(GOOGLE_SHEET_ID)

            # Main worksheet
            try:
                main_ws = sheet.worksheet(GOOGLE_SHEET_TAB_NAME)
            except gspread.WorksheetNotFound:
                main_ws = sheet.sheet1

            # History worksheet (optional)
            try:
                history_ws = sheet.worksheet(GOOGLE_HISTORY_TAB_NAME)
            except gspread.WorksheetNotFound:
                history_ws = None

            return main_ws, history_ws

        try:
            main_ws, history_ws = await asyncio.to_thread(_connect_sync)
            self._worksheet = main_ws
            self._history_worksheet = history_ws
            self._gsheets_ready.set()

            log.info("[DMV] Connected to Google Sheet tab: %s", self._worksheet.title)
            if not self._history_worksheet:
                log.warning("[DMV] '%s' tab not found; history appends will be skipped.", GOOGLE_HISTORY_TAB_NAME)

        except Exception as e:
            log.exception("[DMV] Failed to connect to Google Sheets: %s", e)
            self._worksheet = None
            self._history_worksheet = None
            self._gsheets_ready.clear()

    # -------------------------
    # DB helpers
    # -------------------------
    async def _migrate_licenses_table(self):
        db: aiosqlite.Connection = self.bot.db

        # If the table doesn't exist yet, nothing to migrate
        async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='licenses'"
        ) as cur:
            exists = await cur.fetchone()
        if not exists:
            return

        async with db.execute("PRAGMA table_info(licenses)") as cur:
            rows = await cur.fetchall()

        existing_cols = {r[1] for r in rows}  # r[1] = column name

        async def add_col(sql: str):
            try:
                await db.execute(sql)
            except Exception:
                # If it already exists or fails for some reason, don't crash startup
                pass

        if "license_type" not in existing_cols:
            await add_col("ALTER TABLE licenses ADD COLUMN license_type TEXT")
        if "license_code" not in existing_cols:
            await add_col("ALTER TABLE licenses ADD COLUMN license_code TEXT")
        if "issued_at" not in existing_cols:
            await add_col("ALTER TABLE licenses ADD COLUMN issued_at TEXT")
        if "expires_at" not in existing_cols:
            await add_col("ALTER TABLE licenses ADD COLUMN expires_at TEXT")

        await db.commit()

    async def _get_or_create_record(self, discord_id: int) -> int:
        db: aiosqlite.Connection = self.bot.db
        async with db.execute(
            "SELECT total_points FROM dmv_records WHERE discord_id = ?",
            (discord_id,),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            await db.execute(
                "INSERT INTO dmv_records (discord_id, total_points) VALUES (?, 0)",
                (discord_id,),
            )
            await db.commit()
            return 0

        return int(row[0])

    async def _update_points(
        self,
        discord_id: int,
        code: str,
        points: int,
        title: str,
        reason: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Adds points and logs to history.
        Returns (new_total_points, history_row_id).
        """
        db: aiosqlite.Connection = self.bot.db

        current = await self._get_or_create_record(discord_id)
        new_total = current + points

        await db.execute(
            "UPDATE dmv_records SET total_points = ? WHERE discord_id = ?",
            (new_total, discord_id),
        )

        cur = await db.execute(
            """
            INSERT INTO dmv_history (discord_id, code, title, points, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                discord_id,
                code,
                title,
                points,
                reason or "",
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )

        await db.commit()
        history_id = int(cur.lastrowid or 0)
        return new_total, history_id

    async def _fetch_history(self, discord_id: int) -> List[Tuple[str, str, int, str, str]]:
        db: aiosqlite.Connection = self.bot.db
        async with db.execute(
            """
            SELECT code, title, points, reason, timestamp
            FROM dmv_history
            WHERE discord_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (discord_id, HISTORY_MAX_FETCH),
        ) as cur:
            rows = await cur.fetchall()

        # type: (code, title, points, reason, timestamp)
        return [(r[0], r[1] or "", int(r[2]), r[3] or "", r[4] or "") for r in rows]

    async def _fetch_license_info(self, discord_id: int) -> Optional[LicenseInfo]:
        db: aiosqlite.Connection = self.bot.db
        async with db.execute(
            """
            SELECT roblox_username, roblox_display, roleplay_name,
                   age, address, eye_color, height,
                   license_number, license_type, license_code,
                   issued_at, expires_at
            FROM licenses
            WHERE discord_id = ?
            """,
            (discord_id,),
        ) as cur:
            row = await cur.fetchone()

        if not row:
            return None

        return LicenseInfo(
            roblox_username=row[0] or "",
            roblox_display=row[1] or "",
            roleplay_name=row[2] or "",
            age=row[3],
            address=row[4] or "",
            eye_color=row[5] or "",
            height=row[6] or "",
            license_number=row[7] or "",
            license_type=row[8] or "",
            license_code=row[9] or "",
            issued_at=row[10] or "",
            expires_at=row[11] or "",
        )

    # -------------------------
    # Google Sheets helpers (non-blocking wrappers)
    # -------------------------

    async def _gsheets_retry(self, func, *args, **kwargs):
        # Simple exponential backoff for transient issues
        delays = (0.5, 1.0, 2.0, 4.0)
        last_exc = None
        for d in delays:
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                last_exc = e
                await asyncio.sleep(d)
        raise last_exc  # type: ignore

    async def _update_google_sheet_row(self, member: discord.abc.User, license_info: Optional[LicenseInfo], total_points: int):
        if not self._worksheet:
            return

        ws = self._worksheet
        discord_id = str(member.id)
        discord_tag = str(member)
        now = datetime.utcnow().isoformat(timespec="seconds")

        def _do_update():
            # Try to find row by Discord ID in column A
            try:
                cell = ws.find(discord_id, in_column=1)
                row = cell.row
            except Exception:
                # Append new row at bottom
                row = len(ws.col_values(1)) + 1

            li = license_info or LicenseInfo()

            ws.update(
                f"A{row}:L{row}",
                [[
                    discord_id,
                    discord_tag,
                    li.roblox_username,
                    li.roblox_display,
                    li.roleplay_name,
                    li.license_number,
                    li.license_type,
                    li.license_code,
                    total_points,
                    li.issued_at,
                    li.expires_at,
                    now,
                ]],
            )

        await self._gsheets_retry(_do_update)

    async def _append_dmv_history_sheet(
        self,
        member: discord.abc.User,
        license_info: Optional[LicenseInfo],
        code: str,
        points: int,
        reason: Optional[str],
        officer: discord.abc.User,
        case_number: str,
    ):
        if not self._history_worksheet:
            return

        ws = self._history_worksheet
        li = license_info or LicenseInfo()

        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            str(member.id),
            str(member),
            li.roblox_username,
            li.roleplay_name,
            li.license_number,
            code,
            points,
            str(officer),
            case_number,
            reason or "",
        ]

        def _do_append():
            ws.append_row(row, value_input_option="USER_ENTERED")

        await self._gsheets_retry(_do_append)

    # -------------------------
    # Response helper (works for prefix + slash via hybrid)
    # -------------------------

    async def _reply(self, ctx: commands.Context, content: Optional[str] = None, *, embed: Optional[discord.Embed] = None, ephemeral: bool = False, view: Optional[discord.ui.View] = None):
        # Hybrid ctx supports ephemeral only when invoked as interaction
        if ctx.interaction:
            return await ctx.send(content=content, embed=embed, ephemeral=ephemeral, view=view)
        return await ctx.send(content=content, embed=embed, view=view)

    # =========================
    # COMMANDS (Advanced Slash via Hybrid)
    # =========================

    @commands.hybrid_group(name="dmv", invoke_without_command=True, with_app_command=True)
    async def dmv(self, ctx: commands.Context):
        """DMV system commands."""
        await self._reply(ctx, "Use `/dmv add`, `/dmv points`, `/dmv history`, `/dmv license`.", ephemeral=True)

    # ---- /dmv add ----
    @dmv.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def dmv_add(
        self,
        ctx: commands.Context,
        member: discord.Member,
        code: str,
        points: int,
        *,
        reason: Optional[str] = None,
    ):
        """
        /dmv add member code points reason
        Logs a DMV citation and updates Sheets.
        """
        if points <= 0:
            return await self._reply(ctx, "Points must be a **positive** number.", ephemeral=True)

        # Avoid double submits, and keep totals consistent
        async with self._get_lock(member.id):
            # Defer for slash (Sheets can take time)
            if ctx.interaction:
                await ctx.defer(ephemeral=True)

            title = code  # You can map codes -> titles later if you want

            new_total, history_id = await self._update_points(
                member.id,
                code=code,
                points=points,
                title=title,
                reason=reason,
            )

            suspended = await self._is_suspended(new_total)
            threshold = await self._get_threshold()

            license_info = await self._fetch_license_info(member.id)

            # Case number based on DB history ID (unique & traceable)
            case_number = f"DMV-{datetime.utcnow().strftime('%Y%m%d')}-{history_id:06d}"

            # Update Google Sheets (best-effort; do not fail the command if Sheets is down)
            try:
                await self._update_google_sheet_row(member, license_info, new_total)
            except Exception as e:
                log.warning("[DMV] Sheets row update failed: %s", e)

            try:
                await self._append_dmv_history_sheet(
                    member=member,
                    license_info=license_info,
                    code=code,
                    points=points,
                    reason=reason,
                    officer=ctx.author,
                    case_number=case_number,
                )
            except Exception as e:
                log.warning("[DMV] Sheets history append failed: %s", e)

        # Embed response
        if new_total >= 20:
            color = discord.Color.red()
        elif new_total >= 10:
            color = discord.Color.dark_orange()
        else:
            color = discord.Color.orange()

        embed = discord.Embed(title="DMV Citation Logged", color=color)
        embed.add_field(name="Driver", value=member.mention, inline=False)
        embed.add_field(name="Code", value=code, inline=True)
        embed.add_field(name="Points Added", value=str(points), inline=True)
        embed.add_field(name="New Total Points", value=str(new_total), inline=True)
        embed.add_field(name="Case #", value=case_number, inline=True)

        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)

        embed.add_field(name="Suspension Threshold", value=str(threshold), inline=True)
        if suspended:
            embed.add_field(name="⚠ License Status", value="**SUSPENDED** (threshold exceeded)", inline=False)

        await self._reply(ctx, embed=embed, ephemeral=True)

    # ---- /dmv points ----
    @dmv.command(name="points")
    async def dmv_points(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show current total points for a user."""
        member = member or ctx.author

        total = await self._get_or_create_record(member.id)
        threshold = await self._get_threshold()
        suspended = total >= threshold

        embed = discord.Embed(title="DMV Points", color=discord.Color.blurple())
        embed.add_field(name="Driver", value=str(member), inline=False)
        embed.add_field(name="Total Points", value=str(total), inline=True)
        embed.add_field(name="Suspension Threshold", value=str(threshold), inline=True)
        embed.add_field(name="Status", value="SUSPENDED" if suspended else "ACTIVE", inline=True)

        await self._reply(ctx, embed=embed, ephemeral=True)

    # ---- /dmv history ----
    @dmv.command(name="history")
    async def dmv_history(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show recent DMV history (paginated)."""
        member = member or ctx.author

        rows = await self._fetch_history(member.id)
        view = HistoryView(author_id=ctx.author.id, member=member, rows=rows)

        await self._reply(ctx, embed=view._make_embed(), view=view, ephemeral=True)

    # ---- /dmv license ----
    @dmv.command(name="license")
    async def dmv_license(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show stored license/Roblox details for a user."""
        member = member or ctx.author
        info = await self._fetch_license_info(member.id)

        if not info:
            return await self._reply(ctx, "No license info found for this user in the DMV database.", ephemeral=True)

        embed = discord.Embed(title=f"License Info — {member}", color=discord.Color.green())
        embed.add_field(name="Roblox Username", value=info.roblox_username or "N/A", inline=True)
        embed.add_field(name="Roblox Display", value=info.roblox_display or "N/A", inline=True)
        embed.add_field(name="Roleplay Name", value=info.roleplay_name or "N/A", inline=False)
        embed.add_field(name="License Number", value=info.license_number or "N/A", inline=True)
        embed.add_field(name="License Type", value=info.license_type or "N/A", inline=True)
        embed.add_field(name="License Code", value=info.license_code or "N/A", inline=True)
        embed.add_field(name="Issued At", value=info.issued_at or "N/A", inline=True)
        embed.add_field(name="Expires At", value=info.expires_at or "N/A", inline=True)

        await self._reply(ctx, embed=embed, ephemeral=True)

    # ---- /dmv threshold set ----
    @dmv.command(name="set_threshold")
    @commands.has_permissions(administrator=True)
    async def dmv_set_threshold(self, ctx: commands.Context, value: int):
        """Set the suspension threshold (admin)."""
        if value <= 0:
            return await self._reply(ctx, "Threshold must be a positive integer.", ephemeral=True)

        await self._set_threshold(value)
        await self._reply(ctx, f"Suspension threshold set to **{value}** points.", ephemeral=True)

    # ---- Backwards compatibility: keep your old prefix commands ----
    @commands.command(name="addpoints")
    @commands.has_permissions(manage_messages=True)
    async def addpoints_prefix(
            self,
            ctx: commands.Context,
            member: discord.Member,
            code: str,
            points: int,
            *,
            reason: Optional[str] = None,
    ):
        # This calls /dmv add, which is where suspension handling should live.
        await self.dmv_add(ctx, member, code, points, reason=reason)

    @commands.command(name="dmvlicense")
    async def dmvlicense_prefix(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        await self.dmv_license(ctx, member=member)

    # -------------------------
    # Error handling (clean messages for slash + prefix)
    # -------------------------

    @dmv_add.error
    @dmv_set_threshold.error
    @addpoints_prefix.error
    async def _perm_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            return await self._reply(ctx, "You don’t have permission to use that command.", ephemeral=True)
        if isinstance(error, commands.BadArgument):
            return await self._reply(ctx, "Invalid arguments. Check the command inputs.", ephemeral=True)
        log.exception("[DMV] Command error: %s", error)
        await self._reply(ctx, "Something went wrong while running that command.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DMVCog(bot))
