import discord
from discord.ext import commands

import os
from datetime import datetime
from typing import Optional, Dict, Any

import aiosqlite
import gspread
from google.oauth2.service_account import Credentials

SUSPENSION_THRESHOLD = 16

# =========================
# CONFIG
# =========================

GOOGLE_SA_FILE = "google_service_account.json"
GOOGLE_SHEET_ID = "1cWyhzexhdmblkxFZyGHOlSQ78UDfZ1pwo9Lrc1zMPGQ"
GOOGLE_SHEET_TAB_NAME = "Licenses"  # this is what you told me



class DMVCog(commands.Cog):
    """
    DMV / Points System (Google Sheets only)

    - Uses workforce.db for:
        * dmv_records (total points per discord id)
        * dmv_history (log of offences)
        * licenses (roblox/license info, filled when license is made)
    - Updates Google Sheet tab 'Licenses' whenever points are changed.
    - Does NOT use Excel at all.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._worksheet = None  # Google Sheet worksheet

    def _is_suspended(self, total_points: int) -> bool:
        return total_points >= SUSPENSION_THRESHOLD

    # =========================
    # STARTUP
    # =========================

    @commands.Cog.listener()
    async def on_ready(self):
        # Setup DB tables
        await self._ensure_db_tables()
        # Setup Google Sheet connection
        self._setup_gsheets()
        print("[DMV] DMV cog ready. Google Sheets + DB initialized.")

    async def _ensure_db_tables(self):
        """
        Ensures dmv_records, dmv_history and licenses tables exist.
        Uses bot.db from your setup_hook.
        """
        db: aiosqlite.Connection = self.bot.db

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

        # license info table (should be filled when license is made)
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
    license_type TEXT,     -- ✅ ADD
    license_code TEXT,     -- ✅ ADD
    issued_at TEXT,
    expires_at TEXT
)

            """
        )

        await db.commit()

    def _setup_gsheets(self):
        """
        Connect to Google Sheets (Registered Licenses: LKVCWL),
        and open the 'Licenses' tab.
        """
        if not os.path.exists(GOOGLE_SA_FILE):
            print(f"[DMV] Google service account file not found: {GOOGLE_SA_FILE}")
            return

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(GOOGLE_SA_FILE, scopes=scopes)

        try:
            client = gspread.authorize(creds)
            sheet = client.open_by_key(GOOGLE_SHEET_ID)
            try:
                self._worksheet = sheet.worksheet(GOOGLE_SHEET_TAB_NAME)
            except gspread.WorksheetNotFound:
                print(f"[DMV] Worksheet '{GOOGLE_SHEET_TAB_NAME}' not found; using first sheet.")
                self._worksheet = sheet.sheet1

            print(f"[DMV] Connected to Google Sheet tab: {self._worksheet.title}")
        except Exception as e:
            print("[DMV] Failed to connect to Google Sheets:", e)
            self._worksheet = None

    # =========================
    # DB HELPERS
    # =========================

    async def _get_or_create_record(self, discord_id: int) -> int:
        """
        Get current total points for user. Create user with 0 points if missing.
        """
        db: aiosqlite.Connection = self.bot.db
        async with db.execute(
            "SELECT total_points FROM dmv_records WHERE discord_id = ?",
            (discord_id,),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            await db.execute(
                "INSERT INTO dmv_records (discord_id, total_points) VALUES (?, ?)",
                (discord_id, 0),
            )
            await db.commit()
            return 0

        return row[0]

    async def _update_points(
        self,
        discord_id: int,
        code: str,
        points: int,
        title: str,
        reason: Optional[str] = None,
    ) -> int:
        """
        Add points to a user's DMV record and log it in dmv_history.
        Returns new total.
        """
        db: aiosqlite.Connection = self.bot.db

        current = await self._get_or_create_record(discord_id)
        new_total = current + points

        await db.execute(
            "UPDATE dmv_records SET total_points = ? WHERE discord_id = ?",
            (new_total, discord_id),
        )
        await db.execute(
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
        return new_total

    async def _fetch_history(self, discord_id: int):
        """
        Return list of (code, title, points, reason, timestamp) rows
        sorted newest first.
        """
        db: aiosqlite.Connection = self.bot.db
        async with db.execute(
            """
            SELECT code, title, points, reason, timestamp
            FROM dmv_history
            WHERE discord_id = ?
            ORDER BY id DESC
            LIMIT 25
            """,
            (discord_id,),
        ) as cur:
            rows = await cur.fetchall()
        return rows

    async def _fetch_license_info(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """
        Get Roblox/license data from licenses table.
        This should be filled when the license is created (your Flask endpoint).
        """
        db: aiosqlite.Connection = self.bot.db
        async with db.execute(
            """
            SELECT roblox_username, roblox_display, roleplay_name,
                   age, address, eye_color, height, license_number
            FROM licenses
            WHERE discord_id = ?
            """,
            (discord_id,),
        ) as cur:
            row = await cur.fetchone()

        if not row:
            return None

        return {
            "roblox_username": row[0],
            "roblox_display": row[1],
            "roleplay_name": row[2],
            "age": row[3],
            "address": row[4],
            "eye_color": row[5],
            "height": row[6],
            "license_number": row[7],
        }

    # =========================
    # GOOGLE SHEETS UPDATE
    # =========================
    def _update_google_sheet_row(self, member, license_info, total_points):
        if not self._worksheet:
            print("[DMV] Worksheet not available.")
            return

        ws = self._worksheet
        discord_id = str(member.id)
        discord_tag = str(member)
        now = datetime.utcnow().isoformat(timespec="seconds")

        # Find row by Discord ID
        col_a = ws.col_values(1)
        try:
            row = col_a.index(discord_id) + 1
        except ValueError:
            row = len(col_a) + 1  # new row

        # Pull license info safely
        roblox_username = license_info.get("roblox_username", "") if license_info else ""
        roblox_display = license_info.get("roblox_display", "") if license_info else ""
        roleplay_name = license_info.get("roleplay_name", "") if license_info else ""
        license_number = license_info.get("license_number", "") if license_info else ""

        # Write ALL fields
        ws.update(f"A{row}:H{row}", [[
            discord_id,
            discord_tag,
            roblox_username,
            roblox_display,
            roleplay_name,
            license_number,
            total_points,
            now
        ]])

    def _append_dmv_history_sheet(
            self,
            member,
            license_info,
            code,
            points,
            reason,
            officer
    ):
        if not self._worksheet:
            return

        try:
            sheet = self._worksheet.spreadsheet
            history_ws = sheet.worksheet("DMV History")
        except Exception as e:
            print("[DMV] DMV History sheet not found:", e)
            return

        roblox_username = license_info.get("roblox_username") if license_info else ""
        roleplay_name = license_info.get("roleplay_name") if license_info else ""
        license_number = license_info.get("license_number") if license_info else ""

        case_number = f"DMV-{datetime.utcnow().strftime('%Y%m%d')}-{member.id % 10000}"

        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            str(member.id),
            str(member),
            roblox_username,
            roleplay_name,
            license_number,
            code,
            points,
            str(officer),
            case_number,
            reason or ""
        ]

        history_ws.append_row(row, value_input_option="USER_ENTERED")

    # =========================
    # COMMANDS
    # =========================

    @commands.command(name="addpoints")
    @commands.has_permissions(manage_messages=True)
    async def addpoints(
            self,
            ctx: commands.Context,
            member: discord.Member,
            code: str,
            points: int,
            *,
            reason: Optional[str] = None,
    ):
        """
        ?addpoints @user CODE POINTS [reason]

        Example:
        ?addpoints @User SPD001 4 Speeding in a 35 zone
        """

        if points <= 0:
            return await ctx.send("Points must be a positive number.")

        # Use code as title (or customize later)
        title = code

        # Update DB
        new_total = await self._update_points(
            member.id,
            code,
            points,
            title,
            reason,
        )

        suspended = self._is_suspended(new_total)

        # Fetch license info
        license_info = await self._fetch_license_info(member.id)

        # Update Google Sheet
        self._update_google_sheet_row(member, license_info, new_total)

        # Append DMV history sheet
        self._append_dmv_history_sheet(
            member,
            license_info,
            code,
            points,
            reason,
            ctx.author,
        )

        # Embed
        color = discord.Color.orange()
        if new_total >= 20:
            color = discord.Color.red()
        elif new_total >= 10:
            color = discord.Color.dark_orange()

        embed = discord.Embed(
            title="DMV Citation Logged",
            color=color,
        )
        embed.add_field(name="Driver", value=member.mention, inline=False)
        embed.add_field(name="Code", value=code, inline=True)
        embed.add_field(name="Points Added", value=str(points), inline=True)
        embed.add_field(name="New Total Points", value=str(new_total), inline=True)

        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)

        if suspended:
            embed.add_field(
                name="⚠ License Status",
                value="**SUSPENDED** (point threshold exceeded)",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(name="dmvlicense")
    async def dmvlicense(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        ?dmvlicense [@user]
        Show stored license/Roblox details for a user.
        """
        member = member or ctx.author
        info = await self._fetch_license_info(member.id)

        if not info:
            return await ctx.send("No license info found for this user in DMV database.")

        embed = discord.Embed(
            title=f"License Info — {member}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Roblox Username", value=info["roblox_username"] or "N/A", inline=True)
        embed.add_field(name="Roblox Display", value=info["roblox_display"] or "N/A", inline=True)
        embed.add_field(name="Roleplay Name", value=info["roleplay_name"] or "N/A", inline=False)
        embed.add_field(name="License Number", value=info["license_number"] or "N/A", inline=False)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DMVCog(bot))
