# cogs/economy.py
from __future__ import annotations

import asyncio
import json
import random
import re
import sqlite3
from datetime import datetime, timezone, date
from typing import Dict, Optional, Tuple, List, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ============================================================
# CONFIG
# ============================================================

DB_NAME = "lakeview_shadow.db"
MAIN_GUILD_ID = 1328475009542258688

# Citations can be CREATED from these guilds (but will still route review/log/court to MAIN)
DOC_GUILD_ID = 1452795248387297354
DPS_GUILD_ID = 1445181271344025693
LCFR_GUILD_ID = 1449942107614609442
ALLOWED_CITATION_GUILDS = {MAIN_GUILD_ID, DOC_GUILD_ID, DPS_GUILD_ID, LCFR_GUILD_ID}

# Economy prefix commands allowed ONLY here
ECONOMY_PREFIX_CHANNEL_ID = 1442671320910528664

# Shifts
SALARY_VC_CATEGORY_ID = 1436503704143396914
AFK_CHANNEL_ID = 1442670867963445329
AFK_LIMIT_MINUTES = 2  # drag after 2 minutes

# Approvals
LPD_AUTH_CHANNEL = 1449898275380400404
LCFR_AUTH_CHANNEL = 1449898317323571235
DOC_AUTH_CHANNEL = 1455339511553982536
TRANSFER_AUTH_CHANNEL = 1440448634591121601

# Citations
CITATION_SUBMIT_CHANNEL = 1454978409804337192  # supervisor review channel
CITATION_LOG_CHANNEL = 1454978126500073658     # approved log channel
COURT_CHANNEL = 1454978555707396312            # court revoke channel

# Loans
LOAN_DESK_CHANNEL_ID = 1454646351714455633

# Roles (main server)
BANK_STAFF_ROLE_ID = 1436150175637967012

LPD_ROLE_ID = 1436150189227380786
LPD_SUPERVISOR_ROLE_ID = 1436150183518933033

LCFR_MEMBER_ROLE_ID = 1436150185775595581
LCFR_SUPERVISOR_ROLE_ID = 1436150185431666780

DOC_SUPERVISOR_ROLE_ID = 1455339226823659520
DISPATCH_ROLE_ID = 1436150188447367168

# Embeds
DEFAULT_EMBED_COLOR = 0x757575
DEFAULT_THUMBNAIL = (
    "https://media.discordapp.net/attachments/1377401295220117746/"
    "1437245076945375393/WHITELISTED_NO_BACKGROUND.png?format=webp&quality=lossless"
)

DPS_COLOR = 0x212C44
DPS_THUMBNAIL = (
    "https://cdn.discordapp.com/attachments/1445223165692350606/"
    "1454978855814168770/DPS.png?ex=69530e27&is=6951bca7&hm=ae2fc26a62e81e96330b9ab9a8745383d616d668b8dca8b75e3c4b58300237d0&animated=true"
)

# Pay mapping servers (external)
DPS_PAY_GUILD_ID = 1445181271344025693
LCFR_PAY_GUILD_ID = 1449942107614609442
DOC_PAY_GUILD_ID = 1452795248387297354

# DPS pay roles (in DPS_PAY_GUILD_ID)
DPS_PAY_ROLES: Dict[int, float] = {
    1445185034544873553: 8.00,
    1445185033412280381: 9.00,
    1445184929146077255: 9.50,
    1445184806920130681: 12.00,
    1445184771788636182: 13.00,
    1445184753568321747: 13.50,
}

# LCFR pay roles (in LCFR_PAY_GUILD_ID)
LCFR_PAY_ROLES: Dict[int, float] = {
    1450637490456363020: 8.10,
    1450637485125271705: 9.00,
    1450637483153817761: 9.40,
    1450637480893087835: 10.00,
    1450637478770901105: 13.00,
    1450637476267032697: 14.00,
}

# DOC pay roles (in DOC_PAY_GUILD_ID)
DOC_PAY_ROLES: Dict[int, float] = {
    1454154589954637933: 8.00,
    1454154734809382943: 9.00,
    1454154783253467136: 12.00,
    1454130907127746716: 13.00,
    1454154878627741868: 13.50,
}

BASE_PAY_PER_MINUTE = 8.00

# Scratch cards
SCRATCH_ITEM_NAME = "Scratch Card"
SCRATCH_PRICE = 5.0  # cash ($5)
SCRATCH_DAILY_LIMIT = 1

# Gambling
GAMBLE_COOLDOWN_SECONDS = 90
GAMBLE_WIN_CHANCE = 0.03  # extremely low

# ============================================================
# PENAL CODES (keep your full list here)
# ============================================================

PENAL_CODES: List[str] = [
    "202P — Crimes Against the Person — 2nd Degree Murder",
    "203P — Crimes Against the Person — 3rd Degree Murder",
    "204P — Crimes Against the Person — Attempted Murder",
    "205P — Crimes Against the Person — Aggravated Assault",
    "206P — Crimes Against the Person — Assault",
    "207P (1) — Crimes Against the Person — Criminal Threats",
    "207P (2) — Crimes Against the Person — Threats to Officials",
    "208P — Crimes Against the Person — Battery",
    "209P — Crimes Against the Person — Aggravated Battery",
    "210P — Crimes Against the Person — Domestic Battery",
    "211P — Crimes Against the Person — Abduction",
    "212P — Crimes Against the Person — Hostage Taking",
    "213P (1) — Crimes Against the Person — Restraining Order Violation",
    "213P (2) — Crimes Against the Person — Aggravated Violation of Restraining Order",
    "214P — Crimes Against the Person — Torture",
    "215P — Crimes Against the Person — Child Endangerment",
    "216P — Crimes Against the Person — Child Abuse",
    "217P — Crimes Against the Person — Elder Abuse",
    "218P — Crimes Against the Person — Harassment",
    "219P — Crimes Against the Person — Shooting at a Person",
    "220P — Crimes Against the Person — Identity Theft",
    "221P — Crimes Against the Person — Human Rights Violation",
    "222P — Crimes Against the Person — Criminal Malpractice",
    "223P — Crimes Against the Person — Stalking",
    "224P — Crimes Against the Person — Assassination Services",
    "225P — Crimes Against the Person — Blackmail",
    "226P — Crimes Against the Person — Extortion",
    "227P — Crimes Against the Person — False Imprisonment",
    "228P — Crimes Against the Person — Vehicular Assault",
    "229P — Crimes Against the Person — Criminal Negligence",
    "230P — Crimes Against the Person — Hate-Motivated Harassment",
    "231P — Crimes Against the Person — Witness Intimidation",
    "232P — Crimes Against the Person — Animal Cruelty",
    "301R (1) — Crimes Against Property — Arson",
    "301R (2) — Crimes Against Property — Aggravated Arson",
    "302R — Crimes Against Property — Petty Theft",
    "303R — Crimes Against Property — Grand Theft",
    "304R — Crimes Against Property — Auto Theft",
    "305R — Crimes Against Property — Vandalism",
    "306R — Crimes Against Property — Property Destruction",
    "307R — Crimes Against Property — Defacing Public Property",
    "308R — Crimes Against Property — Damage to Government Property",
    "309R — Crimes Against Property — Shoplifting",
    "310R (1) — Crimes Against Property — Trespassing",
    "310R (2) — Crimes Against Property — Criminal Trespassing",
    "311R — Crimes Against Property — Burglary Tools",
    "312R — Crimes Against Property — Breaking and Entering",
    "313R — Crimes Against Property — Stolen Property Possession",
    "314R — Crimes Against Property — Damage to Emergency Equipment",
    "315R — Crimes Against Property — Embezzlement",
    "316R — Crimes Against Property — Fraud",
    "317R — Crimes Against Property — Misuse of Government Property",
    "318R — Crimes Against Property — Credit Card Fraud",
    "319R — Crimes Against Property — Dumpster Diving (Restricted)",
    "320R — Crimes Against Property — Unlawful Device Tampering",
    "321R — Crimes Against Property — Construction Site Trespass",
    "322R — Crimes Against Property — Tagging/Graffiti",
    "401S — Safety & Order — Disorderly Conduct",
    "402S — Safety & Order — Public Intoxication",
    "403S — Safety & Order — Disturbing the Peace",
    "404S — Safety & Order — Failure to Disperse",
    "405S — Safety & Order — Unlawful Assembly",
    "406S — Safety & Order — Loitering with Criminal Intent",
    "407S — Safety & Order — 911 Abuse",
    "408S — Safety & Order — Roadway Obstruction",
    "409S — Safety & Order — Inciting a Riot",
    "410S — Safety & Order — Participating in a Riot",
    "411S — Safety & Order — Reckless Public Conduct",
    "412S — Safety & Order — Impersonating an Official",
    "413S — Safety & Order — Blocking Emergency Access",
    "414S — Safety & Order — Public Hazard",
    "415S — Safety & Order — Public Endangerment",
    "416S — Safety & Order — Mass Panic",
    "417S — Safety & Order — Minor with Alcohol",
    "418S — Safety & Order — Loitering",
    "419S — Safety & Order — False Emergency Report",
    "420S — Safety & Order — Obstruction of Investigation",
    "421S — Safety & Order — Curfew Violation",
    "422S — Safety & Order — Dangerous Fireworks",
    "423S — Safety & Order — Improper Use of Public Space",
    "424S — Safety & Order — Public Indecency",
    "501F — Firearms & Weapons — Open Carry",
    "502F — Firearms & Weapons — Brandishing",
    "503F — Firearms & Weapons — Firing a Gun in Public",
    "504F — Firearms & Weapons — Illegal Weapons Possession",
    "505F — Firearms & Weapons — Banned Ammo",
    "506F — Firearms & Weapons — Firearm Trafficking",
    "507F — Firearms & Weapons — Weapon in Restricted Area",
    "508F — Firearms & Weapons — Gun Used During Crime",
    "509F — Firearms & Weapons — Felon with a Gun",
    "510F — Firearms & Weapons — Negligent Discharge",
    "511F — Firearms & Weapons — Weapon Threat",
    "512F — Firearms & Weapons — Replica Firearm Misuse",
    "513F — Firearms & Weapons — Firearm While Intoxicated",
    "514F — Firearms & Weapons — Juvenile with Firearm",
    "515F — Firearms & Weapons — No Permit",
    "516F — Firearms & Weapons — Explosive Possession",
    "517F — Firearms & Weapons — Silencer Possession",
    "518F — Firearms & Weapons — Weapon Smuggling",
    "519F — Firearms & Weapons — Improvised Weapon Use",
    "520F — Firearms & Weapons — Armor-Piercing Ammo",
    "601V (1) — Traffic & Vehicles — Speeding 1–15 MPH",
    "601V (2) — Traffic & Vehicles — Speeding 16–34 MPH",
    "601V (3) — Traffic & Vehicles — Felony Speeding 35+ MPH",
    "601V (4) — Traffic & Vehicles — Unpaved Road Speeding",
    "602V — Traffic & Vehicles — Aggressive Driving",
    "603V — Traffic & Vehicles — Reckless Driving",
    "604V — Traffic & Vehicles — Distracted Driving",
    "605V — Traffic & Vehicles — Unlawful U-Turn",
    "606V — Traffic & Vehicles — Failure to Yield to Emergency Vehicles",
    "607V — Traffic & Vehicles — Driving Without Headlights at Night",
    "608V — Traffic & Vehicles — Wrong-Way Driving",
    "609V — Traffic & Vehicles — Off-Road Vehicle Misuse",
    "610V — Traffic & Vehicles — Hit and Run (Property Damage)",
]


async def penal_autocomplete(_: discord.Interaction, current: str):
    cur = (current or "").lower().strip()
    if not cur:
        return [app_commands.Choice(name=p, value=p) for p in PENAL_CODES[:25]]
    matches = [p for p in PENAL_CODES if cur in p.lower()]
    return [app_commands.Choice(name=p, value=p) for p in matches[:25]]


# ============================================================
# UTIL
# ============================================================

def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def ts_discord(ts: int, style: str = "F") -> str:
    return f"<t:{int(ts)}:{style}>"


def money(x: float) -> str:
    return f"${x:,.2f}"


def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)


def normalize_callsign(tok: str) -> str:
    t = (tok or "").strip().upper()
    if t.endswith("-R") or t.endswith("-O"):
        t = t[:-2]
    return t


# ============================================================
# CALLSIGN PARSING + VALIDATION (UPDATED)
# ============================================================

# Required nickname format:
#   "<CALLSIGN> | <roblox>"
#   "<CALLSIGN> I <roblox>"
CALLSIGN_PARSE_RE = re.compile(
    r"^\s*(?P<callsign>.+?)\s*(?:\|\s*|\sI\s+)\s*(?P<rbx>\S+)\s*$",
    re.IGNORECASE
)

# DPS callsign = 1–4 digits
DPS_CALLSIGN_RE = re.compile(r"^\d{1,4}$")

# LCFR apparatus callsign (allow optional hyphen, e.g. E-13 or E13, MCC13, MCC-13)
LCFR_CALLSIGN_RE = re.compile(
    r"^(?:E|R|T|L|TW|S|B|SO|WE|WB|WT|M|MCC|BUS|CAR|BN|CMD|MED)-?(?:13|17)$",
    re.IGNORECASE
)

# DOC callsign prefix
DOC_CALLSIGN_RE = re.compile(r"^!(?:DISPATCH|SECONDARY|SUPERVISOR)$", re.IGNORECASE)


def extract_callsign(display_name: str) -> Optional[str]:
    m = CALLSIGN_PARSE_RE.match(display_name or "")
    if not m:
        return None
    return normalize_callsign(str(m.group("callsign")))


def parse_amount(raw: str, *, max_value: float) -> Optional[float]:
    s = str(raw).strip().lower()
    if s == "all":
        return float(max_value)
    s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    if v <= 0:
        return None
    return v


def parse_user_id(raw: str) -> Optional[int]:
    s = (raw or "").strip()
    m = re.search(r"(\d{15,25})", s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


async def respond_safely(
    itx: discord.Interaction,
    *,
    content: str | None = None,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
):
    kwargs: Dict[str, Any] = {"ephemeral": ephemeral}
    if content is not None:
        kwargs["content"] = content
    if embed is not None:
        kwargs["embed"] = embed
    if view is not None:
        kwargs["view"] = view

    try:
        if not itx.response.is_done():
            await itx.response.send_message(**kwargs)
        else:
            await itx.followup.send(**kwargs)
    except (discord.NotFound, discord.InteractionResponded):
        try:
            if itx.channel:
                fallback: Dict[str, Any] = {}
                if content is not None:
                    fallback["content"] = content
                if embed is not None:
                    fallback["embed"] = embed
                if view is not None:
                    fallback["view"] = view
                await itx.channel.send(**fallback)
        except Exception:
            pass


async def get_external_member(bot: commands.Bot, guild_id: int, uid: int) -> Optional[discord.Member]:
    g = bot.get_guild(guild_id)
    if not g:
        return None
    m = g.get_member(uid)
    if m:
        return m
    try:
        return await g.fetch_member(uid)
    except Exception:
        return None


def highest_rate(member: Optional[discord.Member], mapping: Dict[int, float]) -> Optional[float]:
    if not member:
        return None
    best: Optional[float] = None
    for r in member.roles:
        if r.id in mapping:
            val = mapping[r.id]
            if best is None or val > best:
                best = val
    return best


# ============================================================
# DATABASE + MIGRATIONS
# ============================================================

def column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return bool(row)


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = asyncio.Lock()
        self.create_tables()
        self.repair_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    cash REAL DEFAULT 0,
                    bank REAL DEFAULT 5000
                )
            """)

            # store dept/callsign/rate so we can split shifts cleanly
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS active_shifts (
                    uid TEXT PRIMARY KEY,
                    minutes INTEGER DEFAULT 0,
                    gross REAL DEFAULT 0,
                    start_ts INTEGER DEFAULT 0,
                    last_seen_ts INTEGER DEFAULT 0,
                    afk_timer INTEGER DEFAULT 0,
                    dept TEXT DEFAULT '',
                    callsign TEXT DEFAULT '',
                    rate REAL DEFAULT 0
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_tx (
                    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT,
                    receiver_id TEXT,
                    amount REAL,
                    tx_type TEXT,
                    status TEXT DEFAULT 'PENDING',
                    note TEXT DEFAULT NULL,
                    meta TEXT DEFAULT NULL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    uid TEXT,
                    item_name TEXT,
                    qty INTEGER DEFAULT 0,
                    PRIMARY KEY (uid, item_name)
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory_purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT,
                    item_name TEXT,
                    qty INTEGER,
                    purchased_ts INTEGER
                )
            """)

            # scratch daily
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS scratch_daily (
                    uid TEXT PRIMARY KEY,
                    last_buy_date TEXT
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS citations (
                    case_code TEXT PRIMARY KEY,
                    guild_id TEXT,
                    officer_id TEXT,
                    citizen_id TEXT,
                    penal_code TEXT,
                    brief_description TEXT,
                    amount REAL,
                    status TEXT,
                    created_ts INTEGER,
                    decided_ts INTEGER,
                    decided_by TEXT
                )
            """)

            # ✅ FIX: DO NOT DROP LOANS ON STARTUP
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    borrower_id TEXT,
                    amount REAL,
                    reason TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_ts INTEGER,
                    decided_ts INTEGER DEFAULT 0,
                    decided_by TEXT DEFAULT NULL
                )
            """)

            # admin/history audit
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS money_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER,
                    actor_id TEXT,
                    target_id TEXT,
                    action TEXT,
                    account TEXT,
                    amount REAL,
                    before_cash REAL,
                    before_bank REAL,
                    after_cash REAL,
                    after_bank REAL,
                    note TEXT
                )
            """)

            # gamble cooldown
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS gamble_cooldown (
                    uid TEXT PRIMARY KEY,
                    last_ts INTEGER
                )
            """)

    def repair_tables(self):
        # inventory qty
        if table_exists(self.conn, "inventory") and not column_exists(self.conn, "inventory", "qty"):
            with self.conn:
                self.conn.execute("ALTER TABLE inventory ADD COLUMN qty INTEGER DEFAULT 0")

        # active_shifts missing cols
        for col, ddl in [
            ("start_ts", "ALTER TABLE active_shifts ADD COLUMN start_ts INTEGER DEFAULT 0"),
            ("last_seen_ts", "ALTER TABLE active_shifts ADD COLUMN last_seen_ts INTEGER DEFAULT 0"),
            ("afk_timer", "ALTER TABLE active_shifts ADD COLUMN afk_timer INTEGER DEFAULT 0"),
            ("dept", "ALTER TABLE active_shifts ADD COLUMN dept TEXT DEFAULT ''"),
            ("callsign", "ALTER TABLE active_shifts ADD COLUMN callsign TEXT DEFAULT ''"),
            ("rate", "ALTER TABLE active_shifts ADD COLUMN rate REAL DEFAULT 0"),
        ]:
            if table_exists(self.conn, "active_shifts") and not column_exists(self.conn, "active_shifts", col):
                with self.conn:
                    self.conn.execute(ddl)

        # pending_tx note/meta
        for col, ddl in [
            ("note", "ALTER TABLE pending_tx ADD COLUMN note TEXT DEFAULT NULL"),
            ("meta", "ALTER TABLE pending_tx ADD COLUMN meta TEXT DEFAULT NULL"),
        ]:
            if table_exists(self.conn, "pending_tx") and not column_exists(self.conn, "pending_tx", col):
                with self.conn:
                    self.conn.execute(ddl)

        # scratch_daily.last_buy_date missing
        if table_exists(self.conn, "scratch_daily") and not column_exists(self.conn, "scratch_daily", "last_buy_date"):
            with self.conn:
                self.conn.execute("ALTER TABLE scratch_daily ADD COLUMN last_buy_date TEXT")

        # loans table migration (if you ever had an older loans schema)
        # (add columns only if missing)
        if table_exists(self.conn, "loans"):
            for col, ddl in [
                ("decided_ts", "ALTER TABLE loans ADD COLUMN decided_ts INTEGER DEFAULT 0"),
                ("decided_by", "ALTER TABLE loans ADD COLUMN decided_by TEXT DEFAULT NULL"),
            ]:
                if not column_exists(self.conn, "loans", col):
                    with self.conn:
                        self.conn.execute(ddl)

    async def get_user(self, uid: int | str):
        uid = str(uid)
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE uid=?", (uid,))
        row = cur.fetchone()
        if not row:
            with self.conn:
                self.conn.execute("INSERT INTO users (uid, cash, bank) VALUES (?, 0, 5000)", (uid,))
            cur.execute("SELECT * FROM users WHERE uid=?", (uid,))
            row = cur.fetchone()
        return row


db = Database()

# ============================================================
# INVENTORY HELPERS
# ============================================================

def get_inventory_qty(uid: int, item_name: str) -> int:
    row = db.conn.execute(
        "SELECT qty FROM inventory WHERE uid=? AND item_name=?",
        (str(uid), item_name),
    ).fetchone()
    return int(row["qty"]) if row else 0


def add_inventory_item(uid: int, item_name: str, qty: int, purchased_ts: Optional[int] = None):
    qty = int(qty)
    if qty <= 0:
        return
    with db.conn:
        db.conn.execute("""
            INSERT INTO inventory (uid, item_name, qty)
            VALUES (?, ?, ?)
            ON CONFLICT(uid, item_name) DO UPDATE SET qty = qty + excluded.qty
        """, (str(uid), item_name, qty))
        db.conn.execute("""
            INSERT INTO inventory_purchases (uid, item_name, qty, purchased_ts)
            VALUES (?, ?, ?, ?)
        """, (str(uid), item_name, qty, int(purchased_ts or now_ts())))


def remove_inventory_item(uid: int, item_name: str, qty: int) -> bool:
    qty = int(qty)
    if qty <= 0:
        return False
    cur_qty = get_inventory_qty(uid, item_name)
    if cur_qty < qty:
        return False
    with db.conn:
        db.conn.execute(
            "UPDATE inventory SET qty = qty - ? WHERE uid=? AND item_name=?",
            (qty, str(uid), item_name),
        )
    return True


# ============================================================
# HISTORY HELPERS
# ============================================================

def log_money_history(
    *,
    actor_id: int,
    target_id: int,
    action: str,
    account: str,
    amount: float,
    before_cash: float,
    before_bank: float,
    after_cash: float,
    after_bank: float,
    note: str = "",
):
    with db.conn:
        db.conn.execute("""
            INSERT INTO money_history
            (ts, actor_id, target_id, action, account, amount, before_cash, before_bank, after_cash, after_bank, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_ts(),
            str(actor_id),
            str(target_id),
            action,
            account,
            float(amount),
            float(before_cash),
            float(before_bank),
            float(after_cash),
            float(after_bank),
            note[:500],
        ))


# ============================================================
# VIEWS
# ============================================================

class ApprovalButtons(discord.ui.View):
    """Approves TRANSFERS + SHIFTS + LOANS"""
    def __init__(
        self,
        cog: "EconomyCog",
        tx_id: int,
        tx_type: str,
        sender: str,
        receiver: str,
        amount: float,
        *,
        note: str | None = None,
        meta: str | None = None,
    ):
        super().__init__(timeout=None)
        self.cog = cog
        self.tx_id = int(tx_id)
        self.tx_type = str(tx_type)
        self.sender = str(sender)
        self.receiver = str(receiver)
        self.amount = float(amount)
        self.note = note
        self.meta = meta

    def _allowed(self, member: discord.Member) -> bool:
        if self.tx_type in ("TRANSFER", "LOAN"):
            return has_role(member, BANK_STAFF_ROLE_ID)
        if self.tx_type == "DPS_SHIFT":
            return has_role(member, LPD_SUPERVISOR_ROLE_ID)
        if self.tx_type == "LCFR_SHIFT":
            return has_role(member, LCFR_SUPERVISOR_ROLE_ID)
        if self.tx_type == "DOC_SHIFT":
            return has_role(member, DOC_SUPERVISOR_ROLE_ID)
        return False

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._allowed(itx.user):
            return await respond_safely(itx, content="❌ You can't approve this.", ephemeral=True)

        # ✅ prevent "Interaction failed" on slow DB / API calls
        await itx.response.defer(thinking=True)

        async with db.lock:
            row = db.conn.execute("SELECT status FROM pending_tx WHERE tx_id=?", (self.tx_id,)).fetchone()
            if not row or row["status"] != "PENDING":
                return await itx.edit_original_response(content="⚠️ This request is no longer pending.", view=None)

            if self.tx_type == "TRANSFER":
                s = await db.get_user(self.sender)
                if float(s["bank"]) < self.amount:
                    with db.conn:
                        db.conn.execute("UPDATE pending_tx SET status='DENIED' WHERE tx_id=?", (self.tx_id,))
                    return await itx.edit_original_response(content="❌ Denied: sender no longer has enough bank funds.", view=None)

            with db.conn:
                if self.tx_type in ("DPS_SHIFT", "LCFR_SHIFT", "DOC_SHIFT"):
                    u_before = await db.get_user(self.receiver)
                    before_cash = float(u_before["cash"])
                    before_bank = float(u_before["bank"])
                    db.conn.execute("UPDATE users SET bank=bank+? WHERE uid=?", (self.amount, self.receiver))
                    u_after = await db.get_user(self.receiver)
                    log_money_history(
                        actor_id=itx.user.id,
                        target_id=int(self.receiver),
                        action="SHIFT_APPROVED",
                        account="bank",
                        amount=self.amount,
                        before_cash=before_cash, before_bank=before_bank,
                        after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                        note=self.tx_type
                    )

                elif self.tx_type == "LOAN":
                    u_before = await db.get_user(self.receiver)
                    before_cash = float(u_before["cash"])
                    before_bank = float(u_before["bank"])
                    db.conn.execute("UPDATE users SET bank=bank+? WHERE uid=?", (self.amount, self.receiver))
                    if self.meta:
                        try:
                            loan_id = int(self.meta)
                            db.conn.execute(
                                "UPDATE loans SET status='APPROVED', decided_ts=?, decided_by=? WHERE loan_id=?",
                                (now_ts(), str(itx.user.id), loan_id)
                            )
                        except Exception:
                            pass
                    u_after = await db.get_user(self.receiver)
                    log_money_history(
                        actor_id=itx.user.id,
                        target_id=int(self.receiver),
                        action="LOAN_APPROVED",
                        account="bank",
                        amount=self.amount,
                        before_cash=before_cash, before_bank=before_bank,
                        after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                        note=self.note or ""
                    )

                elif self.tx_type == "TRANSFER":
                    s_before = await db.get_user(self.sender)
                    r_before = await db.get_user(self.receiver)
                    sbc, sbb = float(s_before["cash"]), float(s_before["bank"])
                    rbc, rbb = float(r_before["cash"]), float(r_before["bank"])

                    db.conn.execute("UPDATE users SET bank=bank-? WHERE uid=?", (self.amount, self.sender))
                    db.conn.execute("UPDATE users SET bank=bank+? WHERE uid=?", (self.amount, self.receiver))

                    s_after = await db.get_user(self.sender)
                    r_after = await db.get_user(self.receiver)

                    log_money_history(
                        actor_id=itx.user.id,
                        target_id=int(self.sender),
                        action="TRANSFER_APPROVED_OUT",
                        account="bank",
                        amount=-self.amount,
                        before_cash=sbc, before_bank=sbb,
                        after_cash=float(s_after["cash"]), after_bank=float(s_after["bank"]),
                        note=f"to {self.receiver} | {self.note or ''}"
                    )
                    log_money_history(
                        actor_id=itx.user.id,
                        target_id=int(self.receiver),
                        action="TRANSFER_APPROVED_IN",
                        account="bank",
                        amount=self.amount,
                        before_cash=rbc, before_bank=rbb,
                        after_cash=float(r_after["cash"]), after_bank=float(r_after["bank"]),
                        note=f"from {self.sender} | {self.note or ''}"
                    )

                db.conn.execute("UPDATE pending_tx SET status='APPROVED' WHERE tx_id=?", (self.tx_id,))

        eco = itx.guild.get_channel(ECONOMY_PREFIX_CHANNEL_ID)
        if eco:
            if self.tx_type == "TRANSFER":
                await eco.send(
                    f"✅ **Transfer Approved**: <@{self.sender}> ({self.sender}) → <@{self.receiver}> ({self.receiver}) | **{money(self.amount)}**\n"
                    f"📝 Note: {self.note or 'N/A'}"
                )
            elif self.tx_type == "LOAN":
                await eco.send(
                    f"✅ **Loan Approved**: <@{self.receiver}> ({self.receiver}) | **{money(self.amount)}**\n"
                    f"📝 Reason: {self.note or 'N/A'}"
                )

        if self.tx_type in ("DPS_SHIFT", "LCFR_SHIFT", "DOC_SHIFT"):
            await self.cog.dm_payslip(itx.guild, int(self.receiver), self.amount, self.meta)

        await itx.edit_original_response(content=f"✅ Approved by {itx.user.mention}", view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._allowed(itx.user):
            return await respond_safely(itx, content="❌ You can't deny this.", ephemeral=True)

        await itx.response.defer(thinking=True)

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE pending_tx SET status='DENIED' WHERE tx_id=?", (self.tx_id,))

                if self.tx_type == "LOAN" and self.meta:
                    try:
                        loan_id = int(self.meta)
                        db.conn.execute(
                            "UPDATE loans SET status='DENIED', decided_ts=?, decided_by=? WHERE loan_id=?",
                            (now_ts(), str(itx.user.id), loan_id)
                        )
                    except Exception:
                        pass

        eco = itx.guild.get_channel(ECONOMY_PREFIX_CHANNEL_ID)
        if eco:
            if self.tx_type == "TRANSFER":
                await eco.send(
                    f"❌ **Transfer Denied**: <@{self.sender}> ({self.sender}) → <@{self.receiver}> ({self.receiver}) | **{money(self.amount)}**\n"
                    f"📝 Note: {self.note or 'N/A'}"
                )
            elif self.tx_type == "LOAN":
                await eco.send(
                    f"❌ **Loan Denied**: <@{self.receiver}> ({self.receiver}) | **{money(self.amount)}**\n"
                    f"📝 Reason: {self.note or 'N/A'}"
                )

        await itx.edit_original_response(content=f"❌ Denied by {itx.user.mention}", view=None)


class RevokeCitationView(discord.ui.View):
    def __init__(self, cog: "EconomyCog", case_code: str, citizen_id: int, amount: float):
        super().__init__(timeout=None)
        self.cog = cog
        self.case_code = case_code
        self.citizen_id = int(citizen_id)
        self.amount = float(amount)

    @discord.ui.button(label="Revoke & Refund", style=discord.ButtonStyle.danger)
    async def revoke(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not itx.user.guild_permissions.administrator:
            return await respond_safely(itx, content="Admin only.", ephemeral=True)

        await itx.response.defer(thinking=True)

        async with db.lock:
            u_before = await db.get_user(self.citizen_id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute("UPDATE users SET bank = bank + ? WHERE uid = ?", (self.amount, str(self.citizen_id)))
                db.conn.execute(
                    "UPDATE citations SET status='REVOKED', decided_ts=?, decided_by=? WHERE case_code=?",
                    (now_ts(), str(itx.user.id), self.case_code),
                )
            u_after = await db.get_user(self.citizen_id)
            log_money_history(
                actor_id=itx.user.id,
                target_id=self.citizen_id,
                action="CITATION_REVOKE_REFUND",
                account="bank",
                amount=self.amount,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note=self.case_code
            )

        await itx.edit_original_response(content=f"⚖️ Case `{self.case_code}` revoked & refunded.", view=None)


class CitationActions(discord.ui.View):
    def __init__(
        self,
        cog: "EconomyCog",
        *,
        officer_id: int,
        citizen_id: int,
        case_code: str,
        penal_code: str,
        brief_description: str,
        amount: float,
    ):
        super().__init__(timeout=None)
        self.cog = cog
        self.officer_id = int(officer_id)
        self.citizen_id = int(citizen_id)
        self.case_code = str(case_code)
        self.penal_code = str(penal_code)
        self.brief_description = str(brief_description)
        self.amount = float(amount)

    def _is_supervisor(self, member: discord.Member) -> bool:
        return has_role(member, LPD_SUPERVISOR_ROLE_ID)

    def _updated_embed(self, message: discord.Message, *, new_title: str, new_status: str) -> discord.Embed:
        old = message.embeds[0] if message.embeds else None
        emb = discord.Embed(title=new_title, color=DPS_COLOR)
        emb.set_thumbnail(url=DPS_THUMBNAIL)

        if old:
            for f in old.fields:
                if f.name == "Status:":
                    continue
                emb.add_field(name=f.name, value=f.value, inline=f.inline)

        emb.add_field(name="Status:", value=new_status, inline=False)
        return emb

    @discord.ui.button(label="Approve Citation", style=discord.ButtonStyle.success)
    async def approve(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._is_supervisor(itx.user):
            return await respond_safely(itx, content="Supervisor permissions required.", ephemeral=True)

        await itx.response.defer(thinking=True)

        async with db.lock:
            u_before = await db.get_user(self.citizen_id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute("UPDATE users SET bank = bank - ? WHERE uid = ?", (self.amount, str(self.citizen_id)))
                db.conn.execute(
                    "UPDATE citations SET status='APPROVED', decided_ts=?, decided_by=? WHERE case_code=?",
                    (now_ts(), str(itx.user.id), self.case_code),
                )

            u_after = await db.get_user(self.citizen_id)
            log_money_history(
                actor_id=itx.user.id,
                target_id=self.citizen_id,
                action="CITATION_APPROVED_DEDUCT",
                account="bank",
                amount=-self.amount,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note=self.case_code
            )

        try:
            new_emb = self._updated_embed(itx.message, new_title="Citation Approved:", new_status="Approved (transaction completed).")
            await itx.edit_original_response(embed=new_emb, view=None, content=None)
        except Exception:
            await itx.edit_original_response(content=f"✅ Approved by {itx.user.mention}", view=None)

        await self.cog._post_citation_outputs(
            guild=itx.guild,
            officer_id=self.officer_id,
            citizen_id=self.citizen_id,
            case_code=self.case_code,
            penal_code=self.penal_code,
            brief_description=self.brief_description,
            amount=self.amount,
        )

    @discord.ui.button(label="Deny Citation", style=discord.ButtonStyle.danger)
    async def deny(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._is_supervisor(itx.user):
            return await respond_safely(itx, content="Supervisor permissions required.", ephemeral=True)

        await itx.response.defer(thinking=True)

        async with db.lock:
            with db.conn:
                db.conn.execute(
                    "UPDATE citations SET status='DENIED', decided_ts=?, decided_by=? WHERE case_code=?",
                    (now_ts(), str(itx.user.id), self.case_code),
                )

        try:
            new_emb = self._updated_embed(itx.message, new_title="Citation Denied:", new_status="Denied (no transaction).")
            await itx.edit_original_response(embed=new_emb, view=None, content=None)
        except Exception:
            await itx.edit_original_response(content=f"❌ Denied by {itx.user.mention}", view=None)


# ---------------- SHOP / SCRATCH VIEW

class ShopView(discord.ui.View):
    def __init__(self, cog: "EconomyCog", buyer_id: int, can_buy_today: bool):
        super().__init__(timeout=60)
        self.cog = cog
        self.buyer_id = int(buyer_id)
        if not can_buy_today:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == "buy_scratch":
                    item.disabled = True  # type: ignore

    @discord.ui.button(label="Buy Scratch Card ($5 cash)", style=discord.ButtonStyle.success, custom_id="buy_scratch")
    async def buy_scratch(self, itx: discord.Interaction, _: discord.ui.Button):
        if itx.user.id != self.buyer_id:
            return await respond_safely(itx, content="This isn’t your shop.", ephemeral=True)

        await itx.response.defer(ephemeral=True, thinking=True)

        # ✅ UTC-based "daily" limit
        today = datetime.now(timezone.utc).date().isoformat()

        row = db.conn.execute("SELECT last_buy_date FROM scratch_daily WHERE uid=?", (str(itx.user.id),)).fetchone()
        if row and (row["last_buy_date"] or "") == today:
            return await itx.edit_original_response(content="❌ You already bought a scratch card today.", view=None)

        u = await db.get_user(itx.user.id)
        cash = float(u["cash"])
        if cash < SCRATCH_PRICE:
            return await itx.edit_original_response(content="❌ Not enough cash.", view=None)

        async with db.lock:
            u_before = await db.get_user(itx.user.id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute("UPDATE users SET cash=cash-? WHERE uid=?", (float(SCRATCH_PRICE), str(itx.user.id)))
                db.conn.execute("""
                    INSERT INTO scratch_daily (uid, last_buy_date)
                    VALUES (?, ?)
                    ON CONFLICT(uid) DO UPDATE SET last_buy_date=excluded.last_buy_date
                """, (str(itx.user.id), today))
                add_inventory_item(itx.user.id, SCRATCH_ITEM_NAME, 1, purchased_ts=now_ts())

            u_after = await db.get_user(itx.user.id)
            log_money_history(
                actor_id=itx.user.id,
                target_id=itx.user.id,
                action="BUY_SCRATCH",
                account="cash",
                amount=-SCRATCH_PRICE,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note="shop"
            )

        emb = self.cog.econ_embed(title="Purchase Complete", description=f"You purchased **{SCRATCH_ITEM_NAME}**.\nUse `/scratch` or `?scratch`.")
        if itx.guild:
            self.cog.add_footer(emb, itx.guild)
        await itx.edit_original_response(content=None, embed=emb, view=None)


# ---------------- ADMIN DASHBOARD

class AdminMoneyModal(discord.ui.Modal):
    def __init__(self, cog: "EconomyCog", action: str):
        super().__init__(title=f"Economy Admin: {action}")
        self.cog = cog
        self.action = action  # ADD / REMOVE / SET

        self.target = discord.ui.TextInput(label="Target user (ID or mention)", placeholder="123... or @user", required=True)
        self.account = discord.ui.TextInput(label="Account (cash/bank)", placeholder="bank", required=True, default="bank")
        self.amount = discord.ui.TextInput(label="Amount", placeholder="5000 or 6,835", required=True)

        self.add_item(self.target)
        self.add_item(self.account)
        self.add_item(self.amount)

    async def on_submit(self, itx: discord.Interaction):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not has_role(itx.user, BANK_STAFF_ROLE_ID):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)

        uid = parse_user_id(str(self.target.value))
        if not uid:
            return await respond_safely(itx, content="❌ Invalid user.", ephemeral=True)

        acc = (str(self.account.value).strip().lower() or "bank")
        if acc not in ("cash", "bank"):
            return await respond_safely(itx, content="❌ Account must be `cash` or `bank`.", ephemeral=True)

        raw_amt = str(self.amount.value).strip().replace(",", "")
        try:
            amt = float(raw_amt)
        except Exception:
            return await respond_safely(itx, content="❌ Invalid amount.", ephemeral=True)
        if amt < 0:
            return await respond_safely(itx, content="❌ Amount must be >= 0.", ephemeral=True)

        await itx.response.defer(ephemeral=True, thinking=True)

        async with db.lock:
            u_before = await db.get_user(uid)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                if self.action == "ADD":
                    db.conn.execute(f"UPDATE users SET {acc} = {acc} + ? WHERE uid=?", (amt, str(uid)))
                elif self.action == "REMOVE":
                    db.conn.execute(f"UPDATE users SET {acc} = MAX({acc} - ?, 0) WHERE uid=?", (amt, str(uid)))
                else:  # SET
                    db.conn.execute(f"UPDATE users SET {acc} = ? WHERE uid=?", (amt, str(uid)))

            u_after = await db.get_user(uid)
            after_cash = float(u_after["cash"])
            after_bank = float(u_after["bank"])

            log_money_history(
                actor_id=itx.user.id,
                target_id=uid,
                action=f"ADMIN_{self.action}",
                account=acc,
                amount=amt if self.action != "REMOVE" else -amt,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=after_cash, after_bank=after_bank,
                note="dashboard"
            )

        emb = self.cog.econ_embed(
            title="Admin Update Complete",
            description=f"Target: <@{uid}> (`{uid}`)\nAccount: `{acc}`\nAction: `{self.action}`\nNew balances: Bank {money(after_bank)} | Cash {money(after_cash)}"
        )
        self.cog.add_footer(emb, itx.guild)
        await itx.edit_original_response(embed=emb, content=None, view=None)


class AdminHistoryModal(discord.ui.Modal):
    def __init__(self, cog: "EconomyCog"):
        super().__init__(title="Economy Admin: View History")
        self.cog = cog
        self.target = discord.ui.TextInput(label="Target user (ID or mention)", placeholder="123... or @user", required=True)
        self.add_item(self.target)

    async def on_submit(self, itx: discord.Interaction):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not has_role(itx.user, BANK_STAFF_ROLE_ID):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)

        uid = parse_user_id(str(self.target.value))
        if not uid:
            return await respond_safely(itx, content="❌ Invalid user.", ephemeral=True)

        await itx.response.defer(ephemeral=True, thinking=True)

        rows = db.conn.execute("""
            SELECT ts, actor_id, action, account, amount, before_cash, before_bank, after_cash, after_bank, note
            FROM money_history
            WHERE target_id = ?
            ORDER BY id DESC
            LIMIT 15
        """, (str(uid),)).fetchall()

        emb = self.cog.econ_embed(title="Money History", description=f"Target: <@{uid}> (`{uid}`)")
        if not rows:
            emb.add_field(name="Logs:", value="No history found.", inline=False)
        else:
            lines = []
            for r in rows:
                lines.append(
                    f"{ts_discord(int(r['ts']), 'R')} • `{r['action']}` • `{r['account']}` • `{money(float(r['amount']))}`\n"
                    f"By: <@{r['actor_id']}> • Note: {r['note'] or 'N/A'}\n"
                    f"Bank {money(float(r['before_bank']))} → {money(float(r['after_bank']))} | "
                    f"Cash {money(float(r['before_cash']))} → {money(float(r['after_cash']))}"
                )
            emb.add_field(name="Recent Entries:", value="\n\n".join(lines)[:4000], inline=False)

        self.cog.add_footer(emb, itx.guild)
        await itx.edit_original_response(embed=emb, content=None, view=None)


class AdminDashboardView(discord.ui.View):
    def __init__(self, cog: "EconomyCog"):
        super().__init__(timeout=120)
        self.cog = cog

    def _allowed(self, itx: discord.Interaction) -> bool:
        return bool(itx.guild and isinstance(itx.user, discord.Member) and has_role(itx.user, BANK_STAFF_ROLE_ID))

    @discord.ui.button(label="Add Money", style=discord.ButtonStyle.success)
    async def add_money(self, itx: discord.Interaction, _: discord.ui.Button):
        if not self._allowed(itx):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)
        await itx.response.send_modal(AdminMoneyModal(self.cog, "ADD"))

    @discord.ui.button(label="Remove Money", style=discord.ButtonStyle.danger)
    async def remove_money(self, itx: discord.Interaction, _: discord.ui.Button):
        if not self._allowed(itx):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)
        await itx.response.send_modal(AdminMoneyModal(self.cog, "REMOVE"))

    @discord.ui.button(label="Set Balance", style=discord.ButtonStyle.primary)
    async def set_money(self, itx: discord.Interaction, _: discord.ui.Button):
        if not self._allowed(itx):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)
        await itx.response.send_modal(AdminMoneyModal(self.cog, "SET"))

    @discord.ui.button(label="View History", style=discord.ButtonStyle.secondary)
    async def view_history(self, itx: discord.Interaction, _: discord.ui.Button):
        if not self._allowed(itx):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)
        await itx.response.send_modal(AdminHistoryModal(self.cog))


# ============================================================
# COG
# ============================================================

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # ✅ Cache external pay lookups to avoid rate-limits
        # key: (guild_id, uid) -> (rate, expires_ts)
        self._rate_cache: Dict[Tuple[int, int], Tuple[float, int]] = {}

        self.salary_task.start()
        self.cleanup_task.start()

    def cog_unload(self):
        try:
            self.salary_task.cancel()
        except Exception:
            pass
        try:
            self.cleanup_task.cancel()
        except Exception:
            pass

    # ---------------- embeds
    def add_footer(self, embed: discord.Embed, guild: discord.Guild):
        icon_url = guild.icon.url if guild.icon else None
        embed.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
        return embed

    def econ_embed(self, *, title: str, description: str | None = None) -> discord.Embed:
        emb = discord.Embed(title=title, description=description, color=DEFAULT_EMBED_COLOR)
        emb.set_thumbnail(url=DEFAULT_THUMBNAIL)
        return emb

    def dps_embed(self, *, title: str, description: str | None = None) -> discord.Embed:
        emb = discord.Embed(title=title, description=description, color=DPS_COLOR)
        emb.set_thumbnail(url=DPS_THUMBNAIL)
        return emb

    # ---------------- pay cache
    async def _get_rate_cached(self, *, pay_guild_id: int, uid: int, mapping: Dict[int, float]) -> float:
        key = (pay_guild_id, uid)
        now = now_ts()
        cached = self._rate_cache.get(key)
        if cached and cached[1] > now:
            return float(cached[0])

        ext = await get_external_member(self.bot, pay_guild_id, uid)
        r = highest_rate(ext, mapping)
        rate = float(r if r is not None else BASE_PAY_PER_MINUTE)

        # cache for 5 minutes
        self._rate_cache[key] = (rate, now + 300)
        return rate

    # ---------------- pay logic (STRICT CALLSIGN)
    async def get_pay_context(self, main_member: discord.Member) -> Optional[Tuple[float, str, str]]:
        """
        Returns (rate_per_minute, dept, callsign) OR None if NOT payable.
        Enforces:
          - Nickname must include callsign: "<CALLSIGN> | user" OR "<CALLSIGN> I user"
          - DPS: callsign 1-4 digits + has LPD_ROLE_ID
          - LCFR: apparatus callsign + has LCFR_MEMBER_ROLE_ID
          - DOC: !Dispatch/!Secondary/!Supervisor + has DISPATCH_ROLE_ID
        """
        callsign = extract_callsign(main_member.display_name)
        if not callsign:
            return None

        uid = main_member.id

        # DOC
        if has_role(main_member, DISPATCH_ROLE_ID) and DOC_CALLSIGN_RE.match(callsign):
            rate = await self._get_rate_cached(pay_guild_id=DOC_PAY_GUILD_ID, uid=uid, mapping=DOC_PAY_ROLES)
            return (rate, "DOC", callsign)

        # LCFR
        if has_role(main_member, LCFR_MEMBER_ROLE_ID) and LCFR_CALLSIGN_RE.match(callsign):
            rate = await self._get_rate_cached(pay_guild_id=LCFR_PAY_GUILD_ID, uid=uid, mapping=LCFR_PAY_ROLES)
            return (rate, "LCFR", callsign)

        # DPS
        if has_role(main_member, LPD_ROLE_ID) and DPS_CALLSIGN_RE.match(callsign):
            rate = await self._get_rate_cached(pay_guild_id=DPS_PAY_GUILD_ID, uid=uid, mapping=DPS_PAY_ROLES)
            return (rate, "DPS", callsign)

        return None  # no valid dept/callsign combo => NO PAY

    async def dm_payslip(self, guild: discord.Guild, uid: int, amount: float, meta: Optional[str]):
        start_ts = end_ts = minutes = 0
        rate = 0.0
        dept = "Shift"
        callsign = ""
        try:
            if meta:
                parts = meta.split("|")
                start_ts = int(parts[0])
                end_ts = int(parts[1])
                minutes = int(parts[2])
                rate = float(parts[3])
                dept = str(parts[4])
                if len(parts) >= 6:
                    callsign = str(parts[5])
        except Exception:
            pass

        member = guild.get_member(uid)
        user_obj: discord.abc.Messageable | None = member
        if user_obj is None:
            try:
                user_obj = await self.bot.fetch_user(uid)
            except Exception:
                return

        emb = self.econ_embed(title=f"{dept} Payslip", description="Your shift has been approved and paid.")
        if callsign:
            emb.add_field(name="Callsign:", value=f"`{callsign}`", inline=True)
        emb.add_field(name="Shift Start:", value=ts_discord(start_ts, "F") if start_ts else "N/A", inline=False)
        emb.add_field(name="Shift End:", value=ts_discord(end_ts, "F") if end_ts else "N/A", inline=False)
        emb.add_field(name="Minutes:", value=str(minutes), inline=True)
        emb.add_field(name="Rate (per minute):", value=money(rate), inline=True)
        emb.add_field(name="Total Paid:", value=money(amount), inline=False)
        self.add_footer(emb, guild)

        try:
            await user_obj.send(embed=emb)  # type: ignore
        except Exception:
            pass

    async def _submit_shift_for_approval(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        start_ts: int,
        end_ts: int,
        minutes: int,
        gross: float,
        rate: float,
        dept: str,
        callsign: str,
        reason: str,
    ):
        if minutes <= 0 or gross <= 0:
            return

        if dept == "LCFR":
            auth_channel_id = LCFR_AUTH_CHANNEL
            ping_role = LCFR_SUPERVISOR_ROLE_ID
            tx_type = "LCFR_SHIFT"
        elif dept == "DOC":
            auth_channel_id = DOC_AUTH_CHANNEL
            ping_role = DOC_SUPERVISOR_ROLE_ID
            tx_type = "DOC_SHIFT"
        else:
            auth_channel_id = LPD_AUTH_CHANNEL
            ping_role = LPD_SUPERVISOR_ROLE_ID
            tx_type = "DPS_SHIFT"

        meta = f"{start_ts}|{end_ts}|{minutes}|{rate}|{dept}|{callsign}"

        with db.conn:
            tx_id = db.conn.execute("""
                INSERT INTO pending_tx (sender_id, receiver_id, amount, tx_type, meta)
                VALUES ('GOV', ?, ?, ?, ?)
            """, (str(member.id), float(gross), tx_type, meta)).lastrowid

        chan = guild.get_channel(auth_channel_id)
        if chan:
            emb = self.econ_embed(title=f"{dept} Shift Completed")
            emb.add_field(name="Employee:", value=f"{member.mention} ({member.id})", inline=False)
            emb.add_field(name="Callsign:", value=f"`{callsign}`", inline=True)
            emb.add_field(name="Shift Start:", value=ts_discord(start_ts, "F"), inline=False)
            emb.add_field(name="Shift End:", value=ts_discord(end_ts, "F"), inline=False)
            emb.add_field(name="Minutes:", value=str(minutes), inline=True)
            emb.add_field(name="Rate (per minute):", value=money(rate), inline=True)
            emb.add_field(name="Pay:", value=money(gross), inline=False)
            emb.add_field(name="Reason:", value=reason[:1024], inline=False)
            self.add_footer(emb, guild)

            await chan.send(
                content=f"<@&{ping_role}>",
                embed=emb,
                view=ApprovalButtons(self, tx_id, tx_type, "GOV", str(member.id), float(gross), meta=meta),
            )

    # ============================================================
    # SHIFTS + AFK DRAG (UPDATED)
    # ============================================================

    @tasks.loop(minutes=1)
    async def salary_task(self):
        guild = self.bot.get_guild(MAIN_GUILD_ID)
        if not guild:
            return

        now = now_ts()
        afk_chan = guild.get_channel(AFK_CHANNEL_ID)

        async with db.lock:
            for m in guild.members:
                if not m.voice or not m.voice.channel or not m.voice.channel.category:
                    continue
                if m.voice.channel.category.id != SALARY_VC_CATEGORY_ID:
                    continue

                inactive = bool(
                    m.voice.self_deaf
                    or m.voice.self_mute
                    or (m.voice.channel.id == AFK_CHANNEL_ID)
                )

                row = db.conn.execute(
                    "SELECT * FROM active_shifts WHERE uid=?",
                    (str(m.id),)
                ).fetchone()

                # if inactive, do not accrue minutes, but keep AFK timer
                if inactive:
                    if row:
                        with db.conn:
                            db.conn.execute(
                                "UPDATE active_shifts SET afk_timer = afk_timer + 1, last_seen_ts = ? WHERE uid=?",
                                (now, str(m.id)),
                            )
                        new_row = db.conn.execute(
                            "SELECT afk_timer FROM active_shifts WHERE uid=?",
                            (str(m.id),)
                        ).fetchone()
                        afk_timer = int(new_row["afk_timer"]) if new_row else 0
                    else:
                        ctx = await self.get_pay_context(m)
                        if not ctx:
                            continue
                        rate_now, dept_now, callsign_now = ctx
                        with db.conn:
                            db.conn.execute("""
                                INSERT INTO active_shifts (uid, minutes, gross, start_ts, last_seen_ts, afk_timer, dept, callsign, rate)
                                VALUES (?, 0, 0, ?, ?, 1, ?, ?, ?)
                            """, (str(m.id), now, now, dept_now, callsign_now, float(rate_now)))
                        afk_timer = 1

                    if afk_timer >= AFK_LIMIT_MINUTES:
                        try:
                            if afk_chan and m.voice.channel.id != AFK_CHANNEL_ID:
                                await m.move_to(afk_chan, reason="AFK (2 minutes inactive)")
                        except Exception:
                            pass
                    continue

                # active: must have valid callsign+dept
                ctx = await self.get_pay_context(m)
                if not ctx:
                    if row:
                        minutes = int(row["minutes"] or 0)
                        gross = float(row["gross"] or 0.0)
                        start_ts = int(row["start_ts"] or 0) or (now - minutes * 60)
                        dept_prev = str(row["dept"] or "")
                        callsign_prev = str(row["callsign"] or "")
                        rate_prev = float(row["rate"] or 0.0)

                        with db.conn:
                            db.conn.execute("DELETE FROM active_shifts WHERE uid=?", (str(m.id),))

                        if dept_prev and callsign_prev and rate_prev > 0 and minutes > 0 and gross > 0:
                            await self._submit_shift_for_approval(
                                guild=guild,
                                member=m,
                                start_ts=start_ts,
                                end_ts=now,
                                minutes=minutes,
                                gross=gross,
                                rate=rate_prev,
                                dept=dept_prev,
                                callsign=callsign_prev,
                                reason="Shift ended: callsign/department became invalid (no pay as civilian).",
                            )
                    continue

                rate_now, dept_now, callsign_now = ctx

                # start shift if missing
                if not row:
                    with db.conn:
                        db.conn.execute("""
                            INSERT INTO active_shifts (uid, minutes, gross, start_ts, last_seen_ts, afk_timer, dept, callsign, rate)
                            VALUES (?, 1, ?, ?, ?, 0, ?, ?, ?)
                        """, (str(m.id), float(rate_now), now, now, dept_now, callsign_now, float(rate_now)))
                    continue

                prev_dept = str(row["dept"] or "")
                prev_callsign = str(row["callsign"] or "")
                prev_rate = float(row["rate"] or 0.0)

                # split shift if callsign or dept changed
                if prev_dept != dept_now or prev_callsign != callsign_now:
                    minutes = int(row["minutes"] or 0)
                    gross = float(row["gross"] or 0.0)
                    start_ts = int(row["start_ts"] or 0) or (now - minutes * 60)

                    with db.conn:
                        db.conn.execute("DELETE FROM active_shifts WHERE uid=?", (str(m.id),))

                    if prev_dept and prev_callsign and prev_rate > 0 and minutes > 0 and gross > 0:
                        await self._submit_shift_for_approval(
                            guild=guild,
                            member=m,
                            start_ts=start_ts,
                            end_ts=now,
                            minutes=minutes,
                            gross=gross,
                            rate=prev_rate,
                            dept=prev_dept,
                            callsign=prev_callsign,
                            reason=f"Shift split: `{prev_callsign}`/{prev_dept} → `{callsign_now}`/{dept_now}.",
                        )

                    # start a new segment immediately
                    with db.conn:
                        db.conn.execute("""
                            INSERT INTO active_shifts (uid, minutes, gross, start_ts, last_seen_ts, afk_timer, dept, callsign, rate)
                            VALUES (?, 1, ?, ?, ?, 0, ?, ?, ?)
                        """, (str(m.id), float(rate_now), now, now, dept_now, callsign_now, float(rate_now)))
                    continue

                # normal accrue (use stored rate)
                use_rate = prev_rate if prev_rate > 0 else float(rate_now)
                with db.conn:
                    db.conn.execute("""
                        UPDATE active_shifts
                        SET minutes = minutes + 1,
                            gross = gross + ?,
                            last_seen_ts = ?,
                            afk_timer = 0
                        WHERE uid = ?
                    """, (float(use_rate), now, str(m.id)))

    @salary_task.before_loop
    async def _before_salary_task(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def cleanup_task(self):
        guild = self.bot.get_guild(MAIN_GUILD_ID)
        if not guild:
            return

        now = now_ts()
        cutoff = now - 180  # 3 minutes no updates => finalize shift for approval

        async with db.lock:
            rows = db.conn.execute("SELECT * FROM active_shifts").fetchall()
            for row in rows:
                last_seen = int(row["last_seen_ts"] or 0)
                if last_seen >= cutoff:
                    continue

                uid = int(row["uid"])
                minutes = int(row["minutes"] or 0)
                gross = float(row["gross"] or 0.0)

                start_ts = int(row["start_ts"] or 0)
                if start_ts <= 0:
                    start_ts = now - (minutes * 60)
                end_ts = now

                dept = str(row["dept"] or "")
                callsign = str(row["callsign"] or "")
                rate = float(row["rate"] or 0.0)

                member = guild.get_member(uid)
                with db.conn:
                    db.conn.execute("DELETE FROM active_shifts WHERE uid=?", (str(uid),))

                if not member:
                    continue

                if dept in ("DPS", "LCFR", "DOC") and callsign and rate > 0 and minutes > 0 and gross > 0:
                    await self._submit_shift_for_approval(
                        guild=guild,
                        member=member,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        minutes=minutes,
                        gross=gross,
                        rate=rate,
                        dept=dept,
                        callsign=callsign,
                        reason="Shift ended (timed out / left salary VC).",
                    )

    @cleanup_task.before_loop
    async def _before_cleanup_task(self):
        await self.bot.wait_until_ready()

    # ============================================================
    # CITATIONS OUTPUTS
    # ============================================================

    # ============================================================

    async def _post_citation_outputs(
        self,
        *,
        guild: discord.Guild,
        officer_id: int,
        citizen_id: int,
        case_code: str,
        penal_code: str,
        brief_description: str,
        amount: float,
    ):
        log_chan = guild.get_channel(CITATION_LOG_CHANNEL)
        court_chan = guild.get_channel(COURT_CHANNEL)

        officer_user = guild.get_member(officer_id) or await self.bot.fetch_user(officer_id)
        citizen_user = guild.get_member(citizen_id) or await self.bot.fetch_user(citizen_id)

        u = await db.get_user(citizen_id)
        new_bank_balance = float(u["bank"])
        time_now = now_ts()

        processed = self.dps_embed(
            title="Citation Processed:",
            description="> This citation was approved and the transaction has been completed."
        )
        processed.add_field(name="Officer:", value=f"{getattr(officer_user,'mention','<@'+str(officer_id)+'>')} ({officer_id})", inline=False)
        processed.add_field(name="Citizen:", value=f"{getattr(citizen_user,'mention','<@'+str(citizen_id)+'>')} ({citizen_id})", inline=False)
        processed.add_field(name="Case Code:", value=f"`{case_code}`", inline=True)
        processed.add_field(name="Fine Amount:", value=money(amount), inline=True)
        processed.add_field(name="Penal Code:", value=penal_code, inline=False)
        self.add_footer(processed, guild)

        if log_chan:
            await log_chan.send(embed=processed)

        if court_chan:
            await court_chan.send(embed=processed, view=RevokeCitationView(self, case_code, citizen_id, amount))

        dm_emb = discord.Embed(
            title="DPS | Officer Issued Citation - Completed!",
            description=(
                f"> You were issued an official citation by an officer within the Department of Public Safety on "
                f"{ts_discord(time_now,'F')} — this was reviewed & approved by a supervisor. "
                f"If you feel as though this citation was invalid or inappropriate feel free to appeal it within the "
                f"[Lakeview City Courts](https://discord.gg/7FX6tU5Qzp). Otherwise, the citation stays on your record.\n\n"
                f"Review more information below:"
            ),
            color=DPS_COLOR
        )
        dm_emb.set_thumbnail(url=DPS_THUMBNAIL)
        dm_emb.add_field(name="Officer:", value=f"{getattr(officer_user,'mention','<@'+str(officer_id)+'>')} ({officer_id})", inline=False)
        dm_emb.add_field(name="Violation:", value=(f"**Penal Code:** {penal_code}\n**Description:** {brief_description}"), inline=False)
        dm_emb.add_field(
            name="Financial Summary:",
            value=(
                f"``Fine Amount:`` {money(amount)} (transaction completed)\n"
                f"``Remaining Bank Balance:`` {money(new_bank_balance)}\n"
                f"``Case Code:`` `{case_code}`\n"
                f"``Time:`` {ts_discord(time_now,'F')}"
            ),
            inline=False
        )
        self.add_footer(dm_emb, guild)

        try:
            await citizen_user.send(content=f"{getattr(citizen_user,'mention','')}", embed=dm_emb)  # type: ignore
        except Exception:
            pass

    # ============================================================
    # SLASH COMMANDS
    # ============================================================

    @app_commands.command(name="balance", description="Check bank/cash (optional: view another user)")
    async def balance_slash(self, itx: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or itx.user
        u = await db.get_user(target.id)

        emb = self.econ_embed(title=f"Account Balances: {target.display_name}")
        emb.add_field(name="Bank:", value=money(float(u["bank"])), inline=True)
        emb.add_field(name="Cash:", value=money(float(u["cash"])), inline=True)
        if itx.guild:
            self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=False)

    @app_commands.command(name="leaderboard", description="Top 10 wealthiest citizens")
    async def leaderboard(self, itx: discord.Interaction):
        rows = db.conn.execute("""
            SELECT uid, (cash + bank) AS total
            FROM users
            ORDER BY total DESC
            LIMIT 10
        """).fetchall()

        lines = [f"**{i}.** <@{r['uid']}> — `{money(float(r['total']))}`" for i, r in enumerate(rows, start=1)]
        emb = self.econ_embed(title="Top 10 Wealthiest Citizens", description="\n".join(lines) if lines else "No data yet.")
        if itx.guild:
            self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=False)

    @app_commands.command(name="gamble", description="Coinflip gamble from your CASH (very low win chance)")
    async def gamble_slash(self, itx: discord.Interaction, amount: float):
        row = db.conn.execute("SELECT last_ts FROM gamble_cooldown WHERE uid=?", (str(itx.user.id),)).fetchone()
        last_ts = int(row["last_ts"]) if row else 0
        now = now_ts()
        if (now - last_ts) < GAMBLE_COOLDOWN_SECONDS:
            remain = GAMBLE_COOLDOWN_SECONDS - (now - last_ts)
            return await respond_safely(itx, content=f"⏳ Slow down. Try again {ts_discord(now + remain, 'R')}.", ephemeral=True)

        u = await db.get_user(itx.user.id)
        cash = float(u["cash"])
        if amount <= 0:
            return await respond_safely(itx, content="❌ Amount must be > 0.", ephemeral=True)
        if cash < amount:
            return await respond_safely(itx, content="❌ Not enough cash.", ephemeral=True)

        win = (random.random() < GAMBLE_WIN_CHANCE)

        async with db.lock:
            u_before = await db.get_user(itx.user.id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute("""
                    INSERT INTO gamble_cooldown (uid, last_ts)
                    VALUES (?, ?)
                    ON CONFLICT(uid) DO UPDATE SET last_ts=excluded.last_ts
                """, (str(itx.user.id), now))

                if win:
                    db.conn.execute("UPDATE users SET cash = cash + ? WHERE uid=?", (float(amount), str(itx.user.id)))
                    msg = f"🎲 **WIN!** You gained {money(amount)}."
                    delta = float(amount)
                else:
                    db.conn.execute("UPDATE users SET cash = cash - ? WHERE uid=?", (float(amount), str(itx.user.id)))
                    msg = f"🎲 **LOSS.** You lost {money(amount)}."
                    delta = -float(amount)

            u_after = await db.get_user(itx.user.id)
            log_money_history(
                actor_id=itx.user.id,
                target_id=itx.user.id,
                action="GAMBLE",
                account="cash",
                amount=delta,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note="slash"
            )

        await respond_safely(itx, content=msg, ephemeral=False)

    @app_commands.command(name="transfer", description="Transfer bank funds (Bank Staff must approve)")
    async def transfer_slash(self, itx: discord.Interaction, recipient: discord.Member, amount: float, note: str):
        u = await db.get_user(itx.user.id)
        if amount <= 0:
            return await respond_safely(itx, content="❌ Amount must be > 0.", ephemeral=True)
        if float(u["bank"]) < amount:
            return await respond_safely(itx, content="❌ Insufficient bank funds.", ephemeral=True)

        with db.conn:
            tx_id = db.conn.execute("""
                INSERT INTO pending_tx (sender_id, receiver_id, amount, tx_type, note)
                VALUES (?, ?, ?, 'TRANSFER', ?)
            """, (str(itx.user.id), str(recipient.id), float(amount), str(note))).lastrowid

        if not itx.guild:
            return await respond_safely(itx, content=f"✅ Transfer #{tx_id} submitted.", ephemeral=True)

        chan = itx.guild.get_channel(TRANSFER_AUTH_CHANNEL)
        if chan:
            emb = self.econ_embed(title="Bank Transfer Request")
            emb.add_field(name="From:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
            emb.add_field(name="To:", value=f"{recipient.mention} ({recipient.id})", inline=False)
            emb.add_field(name="Amount:", value=money(amount), inline=False)
            emb.add_field(name="Note:", value=note, inline=False)
            self.add_footer(emb, itx.guild)

            await chan.send(
                content=f"<@&{BANK_STAFF_ROLE_ID}>",
                embed=emb,
                view=ApprovalButtons(self, tx_id, "TRANSFER", str(itx.user.id), str(recipient.id), float(amount), note=note),
            )

        await respond_safely(itx, content=f"✅ Transfer #{tx_id} submitted for Bank Staff review.", ephemeral=True)

    @app_commands.command(name="shop", description="Open the shop")
    async def shop_slash(self, itx: discord.Interaction):
        # ✅ UTC daily limit
        today = datetime.now(timezone.utc).date().isoformat()
        row = db.conn.execute("SELECT last_buy_date FROM scratch_daily WHERE uid=?", (str(itx.user.id),)).fetchone()
        can_buy = not (row and (row["last_buy_date"] or "") == today)

        emb = self.econ_embed(
            title="Shop",
            description=(
                f"**{SCRATCH_ITEM_NAME}** — {money(SCRATCH_PRICE)} cash\n"
                f"> Buy 1 per day.\n"
                f"> Use `/scratch` or `?scratch` to scratch it."
            )
        )
        if itx.guild:
            self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, view=ShopView(self, itx.user.id, can_buy_today=can_buy), ephemeral=True)

    @app_commands.command(name="scratch", description="Use a scratch card (very low win chance)")
    async def scratch_slash(self, itx: discord.Interaction):
        if get_inventory_qty(itx.user.id, SCRATCH_ITEM_NAME) <= 0:
            return await respond_safely(itx, content="❌ You don't have a scratch card. Use `/shop` to buy one.", ephemeral=True)

        async with db.lock:
            ok = remove_inventory_item(itx.user.id, SCRATCH_ITEM_NAME, 1)
            if not ok:
                return await respond_safely(itx, content="❌ You don't have a scratch card.", ephemeral=True)

        roll = random.random()
        if roll < 0.97:
            prize = 0.0
            msg = "🧾 **Scratch Result:** Unlucky… no win this time."
        elif roll < 0.995:
            prize = 10.0
            msg = f"🧾 **Scratch Result:** You won **{money(prize)}**!"
        elif roll < 0.999:
            prize = 50.0
            msg = f"🧾 **Scratch Result:** Nice win! You won **{money(prize)}**!"
        else:
            prize = 500.0
            msg = f"🧾 **Scratch Result:** 🏆 JACKPOT! You won **{money(prize)}**!"

        if prize > 0:
            async with db.lock:
                u_before = await db.get_user(itx.user.id)
                before_cash = float(u_before["cash"])
                before_bank = float(u_before["bank"])

                with db.conn:
                    db.conn.execute("UPDATE users SET cash=cash+? WHERE uid=?", (float(prize), str(itx.user.id)))

                u_after = await db.get_user(itx.user.id)
                log_money_history(
                    actor_id=itx.user.id,
                    target_id=itx.user.id,
                    action="SCRATCH_WIN",
                    account="cash",
                    amount=prize,
                    before_cash=before_cash, before_bank=before_bank,
                    after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                    note="slash"
                )

        await respond_safely(itx, content=msg, ephemeral=False)

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory_slash(self, itx: discord.Interaction):
        rows = db.conn.execute(
            "SELECT item_name, qty FROM inventory WHERE uid=? ORDER BY item_name ASC",
            (str(itx.user.id),)
        ).fetchall()

        if not rows:
            return await respond_safely(itx, content="Your inventory is empty.", ephemeral=True)

        lines = [f"• **{r['item_name']}** × {int(r['qty'])}" for r in rows if int(r["qty"]) > 0]
        emb = self.econ_embed(title=f"{itx.user.display_name}'s Inventory", description="\n".join(lines))
        if itx.guild:
            self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=True)

    @app_commands.command(name="loan_request", description="Request a bank loan (Bank Staff approval required)")
    async def loan_request(self, itx: discord.Interaction, amount: float, reason: str):
        if amount <= 0:
            return await respond_safely(itx, content="❌ Amount must be > 0.", ephemeral=True)

        created = now_ts()
        with db.conn:
            loan_id = db.conn.execute(
                "INSERT INTO loans (borrower_id, amount, reason, status, created_ts) VALUES (?, ?, ?, 'PENDING', ?)",
                (str(itx.user.id), float(amount), reason, created),
            ).lastrowid

            tx_id = db.conn.execute(
                "INSERT INTO pending_tx (sender_id, receiver_id, amount, tx_type, note, meta) VALUES ('BANK', ?, ?, 'LOAN', ?, ?)",
                (str(itx.user.id), float(amount), reason, str(loan_id)),
            ).lastrowid

        if not itx.guild:
            return await respond_safely(itx, content=f"✅ Loan request `{loan_id}` submitted.", ephemeral=True)

        desk = itx.guild.get_channel(LOAN_DESK_CHANNEL_ID)
        if desk:
            emb = self.econ_embed(title="Loan Request Submitted")
            emb.add_field(name="Borrower:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
            emb.add_field(name="Amount:", value=money(amount), inline=True)
            emb.add_field(name="Loan ID:", value=f"`{loan_id}`", inline=True)
            emb.add_field(name="Reason:", value=reason, inline=False)
            self.add_footer(emb, itx.guild)

            await desk.send(
                content=f"<@&{BANK_STAFF_ROLE_ID}>",
                embed=emb,
                view=ApprovalButtons(self, tx_id, "LOAN", "BANK", str(itx.user.id), float(amount), note=reason, meta=str(loan_id)),
            )

        await respond_safely(itx, content=f"✅ Loan request `{loan_id}` submitted for Bank Staff review.", ephemeral=True)

    @app_commands.command(name="economy_admin", description="Bank Staff: Open economy admin dashboard")
    async def economy_admin(self, itx: discord.Interaction):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not has_role(itx.user, BANK_STAFF_ROLE_ID):
            return await respond_safely(itx, content="❌ Bank Staff only.", ephemeral=True)

        emb = self.econ_embed(
            title="Economy Admin Dashboard",
            description="Use the buttons below to manage balances and view history."
        )
        self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, view=AdminDashboardView(self), ephemeral=True)

    @app_commands.command(name="economy_reset_all", description="Admin: Reset everyone to Bank $5,000 and Cash $0")
    async def economy_reset_all(self, itx: discord.Interaction):
        if not itx.guild or itx.guild.id != MAIN_GUILD_ID:
            return await respond_safely(itx, content="❌ This command can only be used in the main server.", ephemeral=True)
        if not isinstance(itx.user, discord.Member) or not itx.user.guild_permissions.administrator:
            return await respond_safely(itx, content="❌ Administrator only.", ephemeral=True)

        cog = self

        class ResetAllView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=45)

            @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
            async def confirm(self, c_itx: discord.Interaction, _: discord.ui.Button):
                if c_itx.user.id != itx.user.id:
                    return await respond_safely(c_itx, content="This isn’t your confirmation.", ephemeral=True)

                await c_itx.response.defer(ephemeral=True, thinking=True)

                async with db.lock:
                    row = db.conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
                    total_users = int(row["n"]) if row else 0

                    with db.conn:
                        db.conn.execute("UPDATE users SET cash=0, bank=5000")
                        db.conn.execute(
                            """
                            INSERT INTO money_history
                            (ts, actor_id, target_id, action, account, amount, before_cash, before_bank, after_cash, after_bank, note)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (now_ts(), str(itx.user.id), "ALL", "ADMIN_RESET_ALL", "both", 0.0, 0.0, 0.0, 0.0, 5000.0, "Set everyone to bank=5000, cash=0"),
                        )

                emb = cog.econ_embed(
                    title="Economy Reset Complete",
                    description=f"✅ Reset **{total_users}** users to **Bank {money(5000)}** and **Cash {money(0)}**."
                )
                cog.add_footer(emb, itx.guild)
                await c_itx.edit_original_response(embed=emb, content=None, view=None)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, c_itx: discord.Interaction, _: discord.ui.Button):
                if c_itx.user.id != itx.user.id:
                    return await respond_safely(c_itx, content="This isn’t your menu.", ephemeral=True)
                await c_itx.response.edit_message(content="Cancelled.", embed=None, view=None)

        warn = self.econ_embed(
            title="Confirm Economy Reset",
            description="⚠️ This will set **EVERYONE** to:\n• Bank: **$5,000**\n• Cash: **$0**\n\nThis cannot be undone."
        )
        self.add_footer(warn, itx.guild)
        await respond_safely(itx, embed=warn, view=ResetAllView(), ephemeral=True)

    # ---------------- citations
    @app_commands.command(name="cite", description="LPD: Issue a citation (requires supervisor approval)")
    async def cite_slash(
        self,
        itx: discord.Interaction,
        citizen: discord.Member,
        penal_code: str,
        amount: float,
        brief_description: str,
    ):
        if not itx.guild:
            return await respond_safely(itx, content="❌ This command can only be used in a server.", ephemeral=True)

        if itx.guild.id not in ALLOWED_CITATION_GUILDS:
            return await respond_safely(itx, content="❌ Citations aren’t enabled in this server.", ephemeral=True)

        main_member = await get_external_member(self.bot, MAIN_GUILD_ID, itx.user.id)
        if not main_member or not has_role(main_member, LPD_ROLE_ID):
            return await respond_safely(itx, content="LPD only.", ephemeral=True)

        if amount <= 0:
            return await respond_safely(itx, content="❌ Amount must be > 0.", ephemeral=True)

        case_code = f"LV-{random.randint(1000, 9999)}"
        created = now_ts()

        confirm = self.dps_embed(
            title="Confirm Citation Submission:",
            description="> Confirm the citation below before it is sent to supervisors."
        )
        confirm.add_field(name="Officer:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
        confirm.add_field(name="Citizen:", value=f"{citizen.mention} ({citizen.id})", inline=False)
        confirm.add_field(name="Case Code:", value=f"`{case_code}`", inline=True)
        confirm.add_field(name="Fine Amount:", value=money(amount), inline=True)
        confirm.add_field(name="Penal Code:", value=penal_code, inline=False)
        confirm.add_field(name="Brief Description:", value=brief_description, inline=False)
        self.add_footer(confirm, itx.guild)

        cog = self

        class ConfirmCite(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=45)

            @discord.ui.button(label="Submit", style=discord.ButtonStyle.success)
            async def submit(self, c_itx: discord.Interaction, _: discord.ui.Button):
                if c_itx.user.id != itx.user.id:
                    return await respond_safely(c_itx, content="This isn’t your confirmation.", ephemeral=True)

                await c_itx.response.defer(ephemeral=True, thinking=True)

                async with db.lock:
                    with db.conn:
                        db.conn.execute("""
                            INSERT INTO citations (
                                case_code, guild_id, officer_id, citizen_id, penal_code, brief_description,
                                amount, status, created_ts, decided_ts, decided_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, 0, NULL)
                        """, (case_code, str(itx.guild.id), str(itx.user.id), str(citizen.id), penal_code, brief_description, float(amount), created))

                main_guild = cog.bot.get_guild(MAIN_GUILD_ID)
                if not main_guild:
                    return await c_itx.edit_original_response(content="❌ Main server not found.", embed=None, view=None)

                chan = main_guild.get_channel(CITATION_SUBMIT_CHANNEL)
                if chan:
                    sup = cog.dps_embed(
                        title="Citation Review Required:",
                        description="> A supervisor must approve or deny this citation."
                    )
                    sup.add_field(name="Officer:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
                    sup.add_field(name="Citizen:", value=f"{citizen.mention} ({citizen.id})", inline=False)
                    sup.add_field(name="Fine Amount:", value=money(amount), inline=True)
                    sup.add_field(name="Case Code:", value=f"`{case_code}`", inline=True)
                    sup.add_field(name="Penal Code:", value=penal_code, inline=False)
                    sup.add_field(name="Status:", value="Pending supervisor review.", inline=False)
                    cog.add_footer(sup, main_guild)

                    await chan.send(
                        content=f"{itx.user.mention} | <@&{LPD_SUPERVISOR_ROLE_ID}>",
                        embed=sup,
                        view=CitationActions(
                            cog,
                            officer_id=itx.user.id,
                            citizen_id=citizen.id,
                            case_code=case_code,
                            penal_code=penal_code,
                            brief_description=brief_description,
                            amount=float(amount),
                        )
                    )

                await c_itx.edit_original_response(content="✅ Citation submitted to supervisors.", embed=None, view=None)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, c_itx: discord.Interaction, _: discord.ui.Button):
                if c_itx.user.id != itx.user.id:
                    return await respond_safely(c_itx, content="This isn’t your menu.", ephemeral=True)
                await c_itx.response.edit_message(content="Cancelled.", embed=None, view=None)

        await respond_safely(itx, embed=confirm, view=ConfirmCite(), ephemeral=True)

    @cite_slash.autocomplete("penal_code")
    async def _cite_autocomplete(self, itx: discord.Interaction, current: str):
        return await penal_autocomplete(itx, current)

    @app_commands.command(name="citationhistory", description="LPD: View a citizen's approved citation history")
    async def citation_history(self, itx: discord.Interaction, citizen: discord.Member):
        if not itx.guild:
            return await respond_safely(itx, content="❌ This command can only be used in a server.", ephemeral=True)

        if itx.guild.id not in ALLOWED_CITATION_GUILDS:
            return await respond_safely(itx, content="❌ Citations aren’t enabled in this server.", ephemeral=True)

        main_member = await get_external_member(self.bot, MAIN_GUILD_ID, itx.user.id)
        if not main_member or not has_role(main_member, LPD_ROLE_ID):
            return await respond_safely(itx, content="LPD only.", ephemeral=True)

        rows = db.conn.execute("""
            SELECT case_code, penal_code, brief_description, amount, created_ts
            FROM citations
            WHERE citizen_id = ? AND status = 'APPROVED'
            ORDER BY created_ts DESC
            LIMIT 25
        """, (str(citizen.id),)).fetchall()

        emb = self.dps_embed(title="Approved Citation History:", description=f"Citizen: {citizen.mention} ({citizen.id})")
        if not rows:
            emb.add_field(name="Records:", value="No approved citations found.", inline=False)
        else:
            text = []
            for r in rows:
                text.append(
                    f"**`{r['case_code']}`** • {money(float(r['amount']))} • {ts_discord(int(r['created_ts']), 'd')}\n"
                    f"{r['penal_code']}\n"
                    f"_{r['brief_description']}_"
                )
            emb.add_field(name="Citations:", value="\n\n".join(text)[:4000], inline=False)

        self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=True)

    # ============================================================
    # PREFIX COMMANDS (only in ECONOMY_PREFIX_CHANNEL_ID)
    # ============================================================

    async def _prefix_gate(self, ctx: commands.Context) -> bool:
        return bool(ctx.guild and ctx.channel and ctx.channel.id == ECONOMY_PREFIX_CHANNEL_ID)

    @commands.command(name="balance")
    async def p_balance(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        if not await self._prefix_gate(ctx):
            return
        target = user or ctx.author
        u = await db.get_user(target.id)

        emb = self.econ_embed(title=f"Account Balances: {target.display_name}")
        emb.add_field(name="Bank:", value=money(float(u["bank"])), inline=True)
        emb.add_field(name="Cash:", value=money(float(u["cash"])), inline=True)
        self.add_footer(emb, ctx.guild)
        await ctx.send(embed=emb)

    @commands.command(name="deposit")
    async def p_deposit(self, ctx: commands.Context, amount: str):
        if not await self._prefix_gate(ctx):
            return
        u = await db.get_user(ctx.author.id)
        cash = float(u["cash"])
        val = parse_amount(amount, max_value=cash)
        if val is None:
            return await ctx.send("❌ Usage: `?deposit all` OR `?deposit 6,835`")
        if cash < val:
            return await ctx.send("❌ Not enough cash.")

        async with db.lock:
            u_before = await db.get_user(ctx.author.id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute(
                    "UPDATE users SET cash = cash - ?, bank = bank + ? WHERE uid=?",
                    (float(val), float(val), str(ctx.author.id))
                )

            u_after = await db.get_user(ctx.author.id)
            log_money_history(
                actor_id=ctx.author.id,
                target_id=ctx.author.id,
                action="DEPOSIT",
                account="cash->bank",
                amount=val,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note="prefix"
            )

        await ctx.send(f"✅ Deposited **{money(val)}** to your bank.")

    @commands.command(name="withdraw")
    async def p_withdraw(self, ctx: commands.Context, amount: str):
        if not await self._prefix_gate(ctx):
            return
        u = await db.get_user(ctx.author.id)
        bank = float(u["bank"])
        val = parse_amount(amount, max_value=bank)
        if val is None:
            return await ctx.send("❌ Usage: `?withdraw all` OR `?withdraw 6,835`")
        if bank < val:
            return await ctx.send("❌ Not enough bank funds.")

        async with db.lock:
            u_before = await db.get_user(ctx.author.id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute(
                    "UPDATE users SET bank = bank - ?, cash = cash + ? WHERE uid=?",
                    (float(val), float(val), str(ctx.author.id))
                )

            u_after = await db.get_user(ctx.author.id)
            log_money_history(
                actor_id=ctx.author.id,
                target_id=ctx.author.id,
                action="WITHDRAW",
                account="bank->cash",
                amount=val,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note="prefix"
            )

        await ctx.send(f"✅ Withdrew **{money(val)}** to your cash.")

    @commands.command(name="gamble")
    async def p_gamble(self, ctx: commands.Context, amount: str):
        if not await self._prefix_gate(ctx):
            return

        row = db.conn.execute("SELECT last_ts FROM gamble_cooldown WHERE uid=?", (str(ctx.author.id),)).fetchone()
        last_ts = int(row["last_ts"]) if row else 0
        now = now_ts()
        if (now - last_ts) < GAMBLE_COOLDOWN_SECONDS:
            remain = GAMBLE_COOLDOWN_SECONDS - (now - last_ts)
            return await ctx.send(f"⏳ Slow down. Try again {ts_discord(now + remain, 'R')}.")

        u = await db.get_user(ctx.author.id)
        cash = float(u["cash"])
        val = parse_amount(amount, max_value=cash)
        if val is None:
            return await ctx.send("❌ Usage: `?gamble all` OR `?gamble 6,835`")
        if cash < val:
            return await ctx.send("❌ Not enough cash.")

        win = (random.random() < GAMBLE_WIN_CHANCE)

        async with db.lock:
            u_before = await db.get_user(ctx.author.id)
            before_cash = float(u_before["cash"])
            before_bank = float(u_before["bank"])

            with db.conn:
                db.conn.execute("""
                    INSERT INTO gamble_cooldown (uid, last_ts)
                    VALUES (?, ?)
                    ON CONFLICT(uid) DO UPDATE SET last_ts=excluded.last_ts
                """, (str(ctx.author.id), now))

                if win:
                    db.conn.execute("UPDATE users SET cash = cash + ? WHERE uid=?", (float(val), str(ctx.author.id)))
                    msg = f"🎲 **WIN!** You gained **{money(val)}**."
                    delta = float(val)
                else:
                    db.conn.execute("UPDATE users SET cash = cash - ? WHERE uid=?", (float(val), str(ctx.author.id)))
                    msg = f"🎲 **LOSS.** You lost **{money(val)}**."
                    delta = -float(val)

            u_after = await db.get_user(ctx.author.id)
            log_money_history(
                actor_id=ctx.author.id,
                target_id=ctx.author.id,
                action="GAMBLE",
                account="cash",
                amount=delta,
                before_cash=before_cash, before_bank=before_bank,
                after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                note="prefix"
            )

        await ctx.send(msg)

    @commands.command(name="inventory")
    async def p_inventory(self, ctx: commands.Context):
        if not await self._prefix_gate(ctx):
            return
        rows = db.conn.execute(
            "SELECT item_name, qty FROM inventory WHERE uid=? ORDER BY item_name ASC",
            (str(ctx.author.id),)
        ).fetchall()

        if not rows:
            return await ctx.send("Your inventory is empty.")

        lines = [f"• **{r['item_name']}** × {int(r['qty'])}" for r in rows if int(r["qty"]) > 0]
        emb = self.econ_embed(title=f"{ctx.author.display_name}'s Inventory", description="\n".join(lines))
        self.add_footer(emb, ctx.guild)
        await ctx.send(embed=emb)

    @commands.command(name="shop")
    async def p_shop(self, ctx: commands.Context):
        if not await self._prefix_gate(ctx):
            return

        today = datetime.now(timezone.utc).date().isoformat()
        row = db.conn.execute("SELECT last_buy_date FROM scratch_daily WHERE uid=?", (str(ctx.author.id),)).fetchone()
        can_buy = not (row and (row["last_buy_date"] or "") == today)

        emb = self.econ_embed(
            title="Shop",
            description=(
                f"**{SCRATCH_ITEM_NAME}** — {money(SCRATCH_PRICE)} cash\n"
                f"> Buy 1 per day.\n"
                f"> Use `?scratch` or `/scratch`."
            )
        )
        self.add_footer(emb, ctx.guild)
        await ctx.send(embed=emb, view=ShopView(self, ctx.author.id, can_buy_today=can_buy))

    @commands.command(name="scratch")
    async def p_scratch(self, ctx: commands.Context):
        if not await self._prefix_gate(ctx):
            return

        if get_inventory_qty(ctx.author.id, SCRATCH_ITEM_NAME) <= 0:
            return await ctx.send("❌ You don't have a scratch card. Use `?shop` to buy one.")

        async with db.lock:
            ok = remove_inventory_item(ctx.author.id, SCRATCH_ITEM_NAME, 1)
            if not ok:
                return await ctx.send("❌ You don't have a scratch card.")

        roll = random.random()
        if roll < 0.97:
            prize = 0.0
            msg = "🧾 **Scratch Result:** Unlucky… no win this time."
        elif roll < 0.995:
            prize = 10.0
            msg = f"🧾 **Scratch Result:** You won **{money(prize)}**!"
        elif roll < 0.999:
            prize = 50.0
            msg = f"🧾 **Scratch Result:** Nice win! You won **{money(prize)}**!"
        else:
            prize = 500.0
            msg = f"🧾 **Scratch Result:** 🏆 JACKPOT! You won **{money(prize)}**!"

        if prize > 0:
            async with db.lock:
                u_before = await db.get_user(ctx.author.id)
                before_cash = float(u_before["cash"])
                before_bank = float(u_before["bank"])

                with db.conn:
                    db.conn.execute("UPDATE users SET cash = cash + ? WHERE uid=?", (float(prize), str(ctx.author.id)))

                u_after = await db.get_user(ctx.author.id)
                log_money_history(
                    actor_id=ctx.author.id,
                    target_id=ctx.author.id,
                    action="SCRATCH_WIN",
                    account="cash",
                    amount=prize,
                    before_cash=before_cash, before_bank=before_bank,
                    after_cash=float(u_after["cash"]), after_bank=float(u_after["bank"]),
                    note="prefix"
                )

        await ctx.send(msg)


# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
