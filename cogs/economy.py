# cogs/economy.py
from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands

import sqlite3
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple, List

# ============================================================
# CONFIG
# ============================================================

MAIN_GUILD_ID = 1328475009542258688
DB_NAME = "lakeview_shadow.db"

# Economy prefix commands are ONLY allowed here:
ECONOMY_PREFIX_CHANNEL_ID = 1442671320910528664

# Shift voice system
SALARY_VC_CATEGORY_ID = 1436503704143396914
AFK_CHANNEL_ID = 1442670867963445329

# Approvals channels
LPD_AUTH_CHANNEL = 1449898275380400404
LCFR_AUTH_CHANNEL = 1449898317323571235
# DOC approvals channel (you gave this ID as "DOC Shift auth role", but it's used as a channel here)
DOC_AUTH_CHANNEL = 1455339511553982536

TRANSFER_AUTH_CHANNEL = 1440448634591121601

# Citation channels
CITATION_SUBMIT_CHANNEL = 1454978409804337192
CITATION_LOG_CHANNEL = 1454978126500073658
COURT_CHANNEL = 1454978555707396312

# Loan desk (ticket threads created here)
LOAN_DESK_CHANNEL_ID = 1454184371824361507

# Roles (MAIN server)
BANK_STAFF_ROLE_ID = 1436150175637967012

LPD_ROLE_ID = 1436150189227380786
LPD_SUPERVISOR_ROLE_ID = 1436150183518933033

LCFR_MEMBER_ROLE_ID = 1436150185775595581
LCFR_SUPERVISOR_ROLE_ID = 1436150185431666780

DOC_SUPERVISOR_ROLE_ID = 1455339226823659520
DISPATCH_ROLE_ID = 1436150188447367168

# Branding (economy embeds)
DEFAULT_EMBED_COLOR = 0x757575
DEFAULT_THUMBNAIL = "https://media.discordapp.net/attachments/1377401295220117746/1437245076945375393/WHITELISTED_NO_BACKGROUND.png?format=webp&quality=lossless"

# Branding (citations)
DPS_COLOR = 0x212C44
DPS_THUMBNAIL = "https://cdn.discordapp.com/attachments/1445223165692350606/1454978855814168770/DPS.png?animated=true"

# Scratch cards
SCRATCH_ITEM_NAME = "Scratch Card"
SCRATCH_PRICE = 250

# ============================================================
# PAY BY ROLES (OTHER SERVERS)
# ============================================================

# You said: DPS uses highest role in this server:
DPS_PAY_GUILD_ID = 1445181271344025693

# You said: LCFR roles live in 1445181271344025693
LCFR_PAY_GUILD_ID = 1449942107614609442

# DOC roles (you didn’t give a separate guild explicitly; adjust if needed)
DOC_PAY_GUILD_ID = 1452795248387297354

# DPS pay roles per minute
DPS_PAY_ROLES: Dict[int, float] = {
    1445185034544873553: 8.00,   # Officer
    1445185033412280381: 9.00,   # Sr. Officer
    1445184929146077255: 9.50,   # Corporal
    1445184806920130681: 12.00,  # Sergeant
    1445184771788636182: 13.00,  # Lieutenant
    1445184753568321747: 13.50,  # Captain
}

# LCFR pay roles per minute
LCFR_PAY_ROLES: Dict[int, float] = {
    1450637490456363020: 8.10,  # FF
    1450637485125271705: 9.00,  # FF2
    1450637483153817761: 9.40,  # Specialist
    1450637480893087835: 10.00, # Trial LT
    1450637478770901105: 13.00, # Lieutenant
    1450637476267032697: 14.00, # Captain
}

# DOC pay roles per minute
DOC_PAY_ROLES: Dict[int, float] = {
    1454154589954637933: 8.00,   # Operator I
    1454154734809382943: 9.00,   # Operator II
    1454154783253467136: 12.00,  # Supervisor
    1454130907127746716: 13.00,  # Sr Supervisor
    1454154878627741868: 13.50,  # Manager
}

BASE_PAY_PER_MINUTE = 8.00

LCFR_CALLSIGNS = {
    "E-13","E-17","R-13","R-17","T-13","T-17","L-13","L-17","TW-13","TW-17","S-13","S-17","B-13","B-17",
    "SO-13","SO-17","WE-13","WE-17","WB-13","WB-17","WT-13","WT-17","M-13","M-17","MCC13","MCC17","BUS13","BUS17",
    "CAR13","CAR17","BN13","BN17","CMD13","CMD17","MED13","MED17"
}
DOC_CALLSIGNS = {"!DISPATCH", "!SUPERVISOR", "!SECONDARY"}

# ============================================================
# PENAL CODES (for autocomplete)
# ============================================================

# Store as FULL strings so “full penal code” is always included.
# Format: "CODE — Name (Category)"
PENAL_CODES: List[str] = [
    "202P — 2nd Degree Murder (Crimes Against the Person)",
    "203P — 3rd Degree Murder (Crimes Against the Person)",
    "204P — Attempted Murder (Crimes Against the Person)",
    "205P — Aggravated Assault (Crimes Against the Person)",
    "206P — Assault (Crimes Against the Person)",
    "207P (1) — Criminal Threats (Crimes Against the Person)",
    "207P (2) — Threats to Officials (Crimes Against the Person)",
    "208P — Battery (Crimes Against the Person)",
    "209P — Aggravated Battery (Crimes Against the Person)",
    "210P — Domestic Battery (Crimes Against the Person)",
    "211P — Abduction (Crimes Against the Person)",
    "212P — Hostage Taking (Crimes Against the Person)",
    "213P (1) — Restraining Order Violation (Crimes Against the Person)",
    "213P (2) — Aggravated Violation of Restraining Order (Crimes Against the Person)",
    "214P — Torture (Crimes Against the Person)",
    "215P — Child Endangerment (Crimes Against the Person)",
    "216P — Child Abuse (Crimes Against the Person)",
    "217P — Elder Abuse (Crimes Against the Person)",
    "218P — Harassment (Crimes Against the Person)",
    "219P — Shooting at a Person (Crimes Against the Person)",
    "220P — Identity Theft (Crimes Against the Person)",
    "221P — Human Rights Violation (Crimes Against the Person)",
    "222P — Criminal Malpractice (Crimes Against the Person)",
    "223P — Stalking (Crimes Against the Person)",
    "224P — Assassination Services (Crimes Against the Person)",
    "225P — Blackmail (Crimes Against the Person)",
    "226P — Extortion (Crimes Against the Person)",
    "227P — False Imprisonment (Crimes Against the Person)",
    "228P — Vehicular Assault (Crimes Against the Person)",
    "229P — Criminal Negligence (Crimes Against the Person)",
    "230P — Hate-Motivated Harassment (Crimes Against the Person)",
    "231P — Witness Intimidation (Crimes Against the Person)",
    "232P — Animal Cruelty (Crimes Against the Person)",
    "301R (1) — Arson (Crimes Against Property)",
    "301R (2) — Aggravated Arson (Crimes Against Property)",
    "302R — Petty Theft (Crimes Against Property)",
    "303R — Grand Theft (Crimes Against Property)",
    "304R — Auto Theft (Crimes Against Property)",
    "305R — Vandalism (Crimes Against Property)",
    "306R — Property Destruction (Crimes Against Property)",
    "307R — Defacing Public Property (Crimes Against Property)",
    "308R — Damage to Government Property (Crimes Against Property)",
    "309R — Shoplifting (Crimes Against Property)",
    "310R (1) — Trespassing (Crimes Against Property)",
    "310R (2) — Criminal Trespassing (Crimes Against Property)",
    "311R — Burglary Tools (Crimes Against Property)",
    "312R — Breaking and Entering (Crimes Against Property)",
    "313R — Stolen Property Possession (Crimes Against Property)",
    "314R — Damage to Emergency Equipment (Crimes Against Property)",
    "315R — Embezzlement (Crimes Against Property)",
    "316R — Fraud (Crimes Against Property)",
    "317R — Misuse of Government Property (Crimes Against Property)",
    "318R — Credit Card Fraud (Crimes Against Property)",
    "319R — Dumpster Diving (Restricted) (Crimes Against Property)",
    "320R — Unlawful Device Tampering (Crimes Against Property)",
    "321R — Construction Site Trespass (Crimes Against Property)",
    "322R — Tagging/Graffiti (Crimes Against Property)",
    "401S — Disorderly Conduct (Safety & Order)",
    "402S — Public Intoxication (Safety & Order)",
    "403S — Disturbing the Peace (Safety & Order)",
    "404S — Failure to Disperse (Safety & Order)",
    "405S — Unlawful Assembly (Safety & Order)",
    "406S — Loitering with Criminal Intent (Safety & Order)",
    "407S — 911 Abuse (Safety & Order)",
    "408S — Roadway Obstruction (Safety & Order)",
    "409S — Inciting a Riot (Safety & Order)",
    "410S — Participating in a Riot (Safety & Order)",
    "411S — Reckless Public Conduct (Safety & Order)",
    "412S — Impersonating an Official (Safety & Order)",
    "413S — Blocking Emergency Access (Safety & Order)",
    "414S — Public Hazard (Safety & Order)",
    "415S — Public Endangerment (Safety & Order)",
    "416S — Mass Panic (Safety & Order)",
    "417S — Minor with Alcohol (Safety & Order)",
    "418S — Loitering (Safety & Order)",
    "419S — False Emergency Report (Safety & Order)",
    "420S — Obstruction of Investigation (Safety & Order)",
    "421S — Curfew Violation (Safety & Order)",
    "422S — Dangerous Fireworks (Safety & Order)",
    "423S — Improper Use of Public Space (Safety & Order)",
    "424S — Public Indecency (Safety & Order)",
    "501F — Open Carry (Firearms & Weapons)",
    "502F — Brandishing (Firearms & Weapons)",
    "503F — Firing a Gun in Public (Firearms & Weapons)",
    "504F — Illegal Weapons Possession (Firearms & Weapons)",
    "505F — Banned Ammo (Firearms & Weapons)",
    "506F — Firearm Trafficking (Firearms & Weapons)",
    "507F — Weapon in Restricted Area (Firearms & Weapons)",
    "508F — Gun Used During Crime (Firearms & Weapons)",
    "509F — Felon with a Gun (Firearms & Weapons)",
    "510F — Negligent Discharge (Firearms & Weapons)",
    "511F — Weapon Threat (Firearms & Weapons)",
    "512F — Replica Firearm Misuse (Firearms & Weapons)",
    "513F — Firearm While Intoxicated (Firearms & Weapons)",
    "514F — Juvenile with Firearm (Firearms & Weapons)",
    "515F — No Permit (Firearms & Weapons)",
    "516F — Explosive Possession (Firearms & Weapons)",
    "517F — Silencer Possession (Firearms & Weapons)",
    "518F — Weapon Smuggling (Firearms & Weapons)",
    "519F — Improvised Weapon Use (Firearms & Weapons)",
    "520F — Armor-Piercing Ammo (Firearms & Weapons)",
    "601V (1) — Speeding 1–15 MPH (Traffic & Vehicles)",
    "601V (2) — Speeding 16–34 MPH (Traffic & Vehicles)",
    "601V (3) — Felony Speeding 35+ MPH (Traffic & Vehicles)",
    "601V (4) — Unpaved Road Speeding (Traffic & Vehicles)",
    "602V — Aggressive Driving (Traffic & Vehicles)",
    "603V — Reckless Driving (Traffic & Vehicles)",
    "604V — Distracted Driving (Traffic & Vehicles)",
    "605V — Unlawful U-Turn (Traffic & Vehicles)",
    "606V — Failure to Yield to Emergency Vehicles (Traffic & Vehicles)",
    "607V — Driving Without Headlights at Night (Traffic & Vehicles)",
    "608V — Wrong-Way Driving (Traffic & Vehicles)",
    "609V — Off-Road Vehicle Misuse (Traffic & Vehicles)",
    "610V — Hit and Run (Property Damage) (Traffic & Vehicles)",
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

def parse_amount_arg(raw: str, *, max_value: float) -> Optional[float]:
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

def first_token(display_name: str) -> str:
    return (display_name or "").strip().split(" ")[0].strip()

def normalize_callsign(tok: str) -> str:
    t = tok.upper()
    if t.endswith("-R") or t.endswith("-O"):
        t = t[:-2]
    return t

def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)

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
# SAFE RESPONDER (fixes view=None crash + dead interactions)
# ============================================================

async def respond_safely(
    itx: discord.Interaction,
    *,
    content: str | None = None,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False
):
    kwargs = {"ephemeral": ephemeral}
    if content is not None:
        kwargs["content"] = content
    if embed is not None:
        kwargs["embed"] = embed
    if view is not None:
        kwargs["view"] = view  # only include when real

    try:
        if not itx.response.is_done():
            await itx.response.send_message(**kwargs)
        else:
            await itx.followup.send(**kwargs)
    except (discord.NotFound, discord.InteractionResponded):
        # token dead or already responded elsewhere → fallback to channel
        try:
            if itx.channel:
                fallback = {}
                if content is not None:
                    fallback["content"] = content
                if embed is not None:
                    fallback["embed"] = embed
                if view is not None:
                    fallback["view"] = view
                await itx.channel.send(**fallback)
        except Exception:
            pass

# ============================================================
# DATABASE
# ============================================================

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
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS active_shifts (
                    uid TEXT PRIMARY KEY,
                    minutes INTEGER DEFAULT 0,
                    gross REAL DEFAULT 0,
                    start_ts INTEGER DEFAULT 0,
                    last_seen_ts INTEGER DEFAULT 0,
                    afk_timer INTEGER DEFAULT 0
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
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    borrower_id TEXT,
                    amount REAL,
                    reason TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_ts INTEGER,
                    decided_ts INTEGER,
                    decided_by TEXT
                )
            """)

    def repair_tables(self):
        # If your old inventory table didn't have qty, add it.
        try:
            self.conn.execute("SELECT qty FROM inventory LIMIT 1")
        except sqlite3.OperationalError:
            with self.conn:
                self.conn.execute("ALTER TABLE inventory ADD COLUMN qty INTEGER DEFAULT 0")

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
# VIEWS (Approvals)
# ============================================================

class ApprovalButtons(discord.ui.View):
    def __init__(self, cog: "EconomyCog", tx_id: int, tx_type: str, sender: str, receiver: str, amount: float, *, note: str | None = None, meta: str | None = None):
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
        # Transfer + Loan approvals: Bank Staff only
        if self.tx_type in ("TRANSFER", "LOAN"):
            return has_role(member, BANK_STAFF_ROLE_ID)

        # Shift approvals: dept supervisors
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

        async with db.lock:
            with db.conn:
                # SHIFT + LOAN pay: add to receiver bank
                if self.tx_type in ("DPS_SHIFT", "LCFR_SHIFT", "DOC_SHIFT", "LOAN"):
                    db.conn.execute("UPDATE users SET bank = bank + ? WHERE uid = ?", (self.amount, self.receiver))

                # TRANSFER: subtract sender bank, add receiver bank
                elif self.tx_type == "TRANSFER":
                    db.conn.execute("UPDATE users SET bank = bank - ? WHERE uid = ?", (self.amount, self.sender))
                    db.conn.execute("UPDATE users SET bank = bank + ? WHERE uid = ?", (self.amount, self.receiver))

                db.conn.execute("UPDATE pending_tx SET status='APPROVED' WHERE tx_id=?", (self.tx_id,))

        # Post acceptance notice for transfers in economy channel (plain message with pings)
        if self.tx_type == "TRANSFER":
            eco = itx.guild.get_channel(ECONOMY_PREFIX_CHANNEL_ID)
            if eco:
                await eco.send(
                    f"✅ **Transfer Approved**: <@{self.sender}> → <@{self.receiver}> | **{money(self.amount)}**\n"
                    f"📝 Note: {self.note or 'N/A'}"
                )

        # Loan accepted notice
        if self.tx_type == "LOAN":
            # mark loan status too if meta has loan_id
            loan_id = self.meta
            async with db.lock:
                with db.conn:
                    if loan_id:
                        db.conn.execute("UPDATE loans SET status='APPROVED', decided_ts=?, decided_by=? WHERE loan_id=?",
                                        (now_ts(), str(itx.user.id), int(loan_id)))
            eco = itx.guild.get_channel(ECONOMY_PREFIX_CHANNEL_ID)
            if eco:
                await eco.send(
                    f"✅ **Loan Approved**: <@{self.receiver}> | **{money(self.amount)}**\n"
                    f"📝 Reason: {self.note or 'N/A'}"
                )

        # DM payslip for shifts
        if self.tx_type in ("DPS_SHIFT", "LCFR_SHIFT", "DOC_SHIFT"):
            await self.cog.dm_payslip(itx.guild, int(self.receiver), self.amount, self.meta)

        await itx.response.edit_message(content=f"✅ Approved by {itx.user.mention}", view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._allowed(itx.user):
            return await respond_safely(itx, content="❌ You can't deny this.", ephemeral=True)

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE pending_tx SET status='DENIED' WHERE tx_id=?", (self.tx_id,))

        # Transfer deny notice
        if self.tx_type == "TRANSFER":
            eco = itx.guild.get_channel(ECONOMY_PREFIX_CHANNEL_ID)
            if eco:
                await eco.send(
                    f"❌ **Transfer Denied**: <@{self.sender}> → <@{self.receiver}> | **{money(self.amount)}**\n"
                    f"📝 Note: {self.note or 'N/A'}"
                )

        if self.tx_type == "LOAN":
            loan_id = self.meta
            async with db.lock:
                with db.conn:
                    if loan_id:
                        db.conn.execute("UPDATE loans SET status='DENIED', decided_ts=?, decided_by=? WHERE loan_id=?",
                                        (now_ts(), str(itx.user.id), int(loan_id)))
            eco = itx.guild.get_channel(ECONOMY_PREFIX_CHANNEL_ID)
            if eco:
                await eco.send(
                    f"❌ **Loan Denied**: <@{self.receiver}> | **{money(self.amount)}**\n"
                    f"📝 Reason: {self.note or 'N/A'}"
                )

        await itx.response.edit_message(content=f"❌ Denied by {itx.user.mention}", view=None)

class CourtRevokeView(discord.ui.View):
    def __init__(self, cog: "EconomyCog", case_code: str, citizen_id: int, amount: float):
        super().__init__(timeout=None)
        self.cog = cog
        self.case_code = case_code
        self.citizen_id = int(citizen_id)
        self.amount = float(amount)

    @discord.ui.button(label="Revoke & Refund", style=discord.ButtonStyle.danger)
    async def revoke(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.user.guild_permissions.administrator:
            return await respond_safely(itx, content="Admin only.", ephemeral=True)

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET bank=bank+? WHERE uid=?", (self.amount, str(self.citizen_id)))
                db.conn.execute("UPDATE citations SET status='REVOKED' WHERE case_code=?", (self.case_code,))

        await itx.response.edit_message(content=f"⚖️ Revoked `{self.case_code}` and refunded {money(self.amount)}.", view=None)

class CitationActions(discord.ui.View):
    def __init__(self, cog: "EconomyCog", *, case_code: str, officer_id: int, citizen_id: int, penal_code: str, brief_description: str, amount: float):
        super().__init__(timeout=None)
        self.cog = cog
        self.case_code = case_code
        self.officer_id = int(officer_id)
        self.citizen_id = int(citizen_id)
        self.penal_code = penal_code
        self.brief_description = brief_description
        self.amount = float(amount)

    def _is_supervisor(self, member: discord.Member) -> bool:
        return has_role(member, LPD_SUPERVISOR_ROLE_ID)

    def _update_status_embed(self, message: discord.Message, *, new_title: str, new_status: str) -> Optional[discord.Embed]:
        if not message.embeds:
            return None
        emb = message.embeds[0].copy()
        emb.title = new_title

        old_fields = list(emb.fields)
        emb.clear_fields()

        found = False
        for f in old_fields:
            if f.name.strip().lower().startswith("status"):
                emb.add_field(name="Status:", value=new_status, inline=False)
                found = True
            else:
                emb.add_field(name=f.name, value=f.value, inline=f.inline)

        if not found:
            emb.add_field(name="Status:", value=new_status, inline=False)
        return emb

    @discord.ui.button(label="Approve Citation", style=discord.ButtonStyle.success)
    async def approve(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._is_supervisor(itx.user):
            return await respond_safely(itx, content="Supervisor permissions required.", ephemeral=True)

        guild = itx.guild

        # Deduct economy & finalize citation
        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET bank = bank - ? WHERE uid = ?", (self.amount, str(self.citizen_id)))
                db.conn.execute("""
                    UPDATE citations
                    SET status='APPROVED', decided_ts=?, decided_by=?
                    WHERE case_code=?
                """, (now_ts(), str(itx.user.id), self.case_code))

        # Update supervisor message status/title
        updated = self._update_status_embed(itx.message, new_title="Citation Approved:", new_status="Approved (transaction completed).")
        if updated:
            await itx.response.edit_message(embed=updated, view=None)
        else:
            await itx.response.edit_message(content=f"✅ Citation Approved by {itx.user.mention}", view=None)

        # Build log embed (approved channel + court)
        officer_user = guild.get_member(self.officer_id) or await self.cog.bot.fetch_user(self.officer_id)
        citizen_user = guild.get_member(self.citizen_id) or await self.cog.bot.fetch_user(self.citizen_id)

        log_emb = discord.Embed(title="DPS | Citation Approved:", color=DPS_COLOR)
        log_emb.set_thumbnail(url=DPS_THUMBNAIL)
        log_emb.add_field(name="Case Code:", value=f"`{self.case_code}`", inline=False)
        log_emb.add_field(name="Officer:", value=f"{officer_user.mention} ({self.officer_id})", inline=False)
        log_emb.add_field(name="Citizen:", value=f"{citizen_user.mention} ({self.citizen_id})", inline=False)
        log_emb.add_field(name="Penal Code:", value=self.penal_code, inline=False)
        log_emb.add_field(name="Fine Amount:", value=money(self.amount), inline=True)
        log_emb.add_field(name="Status:", value="Approved (transaction completed).", inline=True)
        self.cog.add_footer(log_emb, guild)

        log_chan = guild.get_channel(CITATION_LOG_CHANNEL)
        court_chan = guild.get_channel(COURT_CHANNEL)
        if log_chan:
            await log_chan.send(embed=log_emb)
        if court_chan:
            await court_chan.send(embed=log_emb, view=CourtRevokeView(self.cog, self.case_code, self.citizen_id, self.amount))

        # DM the cited person (mention outside embed)
        await self.cog.dm_citation_approved(
            guild=guild,
            officer_id=self.officer_id,
            citizen_id=self.citizen_id,
            penal_code=self.penal_code,
            brief_description=self.brief_description,
            amount=self.amount,
            case_code=self.case_code
        )

    @discord.ui.button(label="Deny Citation", style=discord.ButtonStyle.danger)
    async def deny(self, itx: discord.Interaction, _: discord.ui.Button):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not self._is_supervisor(itx.user):
            return await respond_safely(itx, content="Supervisor permissions required.", ephemeral=True)

        async with db.lock:
            with db.conn:
                db.conn.execute("""
                    UPDATE citations
                    SET status='DENIED', decided_ts=?, decided_by=?
                    WHERE case_code=?
                """, (now_ts(), str(itx.user.id), self.case_code))

        updated = self._update_status_embed(itx.message, new_title="Citation Denied:", new_status="Denied (no transaction).")
        if updated:
            await itx.response.edit_message(embed=updated, view=None)
        else:
            await itx.response.edit_message(content=f"❌ Citation Denied by {itx.user.mention}", view=None)

# ============================================================
# COG
# ============================================================

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.salary_task.start()
        self.cleanup_task.start()

    # ---------------- Embeds ----------------
    def add_footer(self, embed: discord.Embed, guild: discord.Guild):
        icon_url = guild.icon.url if guild.icon else None
        embed.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
        return embed

    def econ_embed(self, *, title: str, description: str | None = None) -> discord.Embed:
        emb = discord.Embed(title=title, description=description, color=DEFAULT_EMBED_COLOR)
        emb.set_thumbnail(url=DEFAULT_THUMBNAIL)
        return emb

    # ---------------- Inventory helpers ----------------
    def add_inventory_item(self, uid: int, item_name: str, qty: int):
        with db.conn:
            db.conn.execute("""
                INSERT INTO inventory (uid, item_name, qty) VALUES (?, ?, ?)
                ON CONFLICT(uid, item_name) DO UPDATE SET qty = qty + excluded.qty
            """, (str(uid), item_name, int(qty)))
            db.conn.execute("""
                INSERT INTO inventory_purchases (uid, item_name, qty, purchased_ts)
                VALUES (?, ?, ?, ?)
            """, (str(uid), item_name, int(qty), now_ts()))

    def get_inventory(self, uid: int) -> List[sqlite3.Row]:
        cur = db.conn.execute("SELECT item_name, qty FROM inventory WHERE uid=? AND qty > 0 ORDER BY item_name ASC", (str(uid),))
        return cur.fetchall()

    def last_purchase_ts(self, uid: int, item_name: str) -> Optional[int]:
        cur = db.conn.execute("""
            SELECT purchased_ts FROM inventory_purchases
            WHERE uid=? AND item_name=?
            ORDER BY purchased_ts DESC LIMIT 1
        """, (str(uid), item_name))
        row = cur.fetchone()
        return int(row["purchased_ts"]) if row else None

    # ---------------- Pay rate logic ----------------
    async def get_pay_rate_and_dept(self, main_member: discord.Member) -> Tuple[float, str]:
        uid = main_member.id
        tok = normalize_callsign(first_token(main_member.display_name))

        # DOC: callsign or dispatch role
        if tok in DOC_CALLSIGNS or has_role(main_member, DISPATCH_ROLE_ID):
            ext = await get_external_member(self.bot, DOC_PAY_GUILD_ID, uid)
            r = highest_rate(ext, DOC_PAY_ROLES)
            return (r if r is not None else BASE_PAY_PER_MINUTE), "DOC"

        # LCFR: has LCFR role in main + callsign matches
        if has_role(main_member, LCFR_MEMBER_ROLE_ID) and tok in LCFR_CALLSIGNS:
            ext = await get_external_member(self.bot, LCFR_PAY_GUILD_ID, uid)
            r = highest_rate(ext, LCFR_PAY_ROLES)
            return (r if r is not None else BASE_PAY_PER_MINUTE), "LCFR"

        # DPS: highest role in DPS guild
        ext = await get_external_member(self.bot, DPS_PAY_GUILD_ID, uid)
        r = highest_rate(ext, DPS_PAY_ROLES)
        return (r if r is not None else BASE_PAY_PER_MINUTE), "DPS"

    # ---------------- Payslip DM ----------------
    async def dm_payslip(self, guild: discord.Guild, uid: int, amount: float, meta: Optional[str]):
        # meta format: "start|end|minutes|rate|dept"
        start_ts = end_ts = minutes = 0
        rate = 0.0
        dept = "Shift"
        try:
            if meta:
                parts = meta.split("|")
                start_ts = int(parts[0])
                end_ts = int(parts[1])
                minutes = int(parts[2])
                rate = float(parts[3])
                dept = str(parts[4])
        except Exception:
            pass

        user = guild.get_member(uid) or await self.bot.fetch_user(uid)
        if not user:
            return

        emb = self.econ_embed(title=f"{dept} Payslip", description="Your shift has been approved and paid.")
        emb.add_field(name="Shift Start:", value=ts_discord(start_ts, "F") if start_ts else "N/A", inline=False)
        emb.add_field(name="Shift End:", value=ts_discord(end_ts, "F") if end_ts else "N/A", inline=False)
        emb.add_field(name="Minutes:", value=str(minutes), inline=True)
        emb.add_field(name="Rate (per minute):", value=money(rate), inline=True)
        emb.add_field(name="Total Paid:", value=money(amount), inline=False)
        self.add_footer(emb, guild)

        try:
            await user.send(embed=emb)
        except Exception:
            pass

    # ---------------- Citation DM ----------------
    async def dm_citation_approved(
        self,
        *,
        guild: discord.Guild,
        officer_id: int,
        citizen_id: int,
        penal_code: str,
        brief_description: str,
        amount: float,
        case_code: str
    ):
        officer_user = guild.get_member(officer_id) or await self.bot.fetch_user(officer_id)
        citizen_user = guild.get_member(citizen_id) or await self.bot.fetch_user(citizen_id)

        u = await db.get_user(citizen_id)
        new_bank_balance = float(u["bank"])
        time_now = now_ts()

        dm_emb = discord.Embed(
            title="DPS | Officer Issued Citation - Completed!",
            description=(
                f"> You were issued an official citation by an officer within the Department of Public Safety on "
                f"{ts_discord(time_now, 'F')} — this was reviewed & approved by a supervisor.\n\n"
                f"If you feel as though this citation was invalid or inappropriate, feel free to appeal it within "
                f"the **Lakeview City Courts**:\n"
                f"https://discord.gg/7FX6tU5Qzp\n\n"
                f"Review more information below:"
            ),
            color=DPS_COLOR
        )
        dm_emb.set_thumbnail(url=DPS_THUMBNAIL)

        dm_emb.add_field(name="Officer:", value=f"{officer_user.mention} ({officer_id})", inline=False)
        dm_emb.add_field(
            name="Violation:",
            value=f"**Penal Code:** {penal_code}\n**Description:** {brief_description}",
            inline=False
        )
        dm_emb.add_field(
            name="Financial Summary:",
            value=(
                f"``Fine Amount:`` {money(amount)} (transaction completed)\n"
                f"``Remaining Bank Balance:`` {money(new_bank_balance)}\n"
                f"``Case Code:`` `{case_code}`"
            ),
            inline=False
        )

        self.add_footer(dm_emb, guild)

        try:
            await citizen_user.send(content=citizen_user.mention, embed=dm_emb)
        except Exception:
            pass

    # ============================================================
    # SLASH COMMANDS
    # ============================================================

    @app_commands.command(name="balance", description="Check your balance (or someone else's).")
    async def balance(self, itx: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or itx.user
        u = await db.get_user(target.id)

        emb = self.econ_embed(title=f"Account Balances: {target.display_name}")
        emb.add_field(name="Bank:", value=money(float(u["bank"])), inline=True)
        emb.add_field(name="Cash:", value=money(float(u["cash"])), inline=True)
        if itx.guild:
            self.add_footer(emb, itx.guild)

        await respond_safely(itx, embed=emb, ephemeral=False)

    @app_commands.command(name="deposit", description="Deposit cash into bank (supports 'all').")
    async def deposit_slash(self, itx: discord.Interaction, amount: str):
        u = await db.get_user(itx.user.id)
        cash = float(u["cash"])
        val = parse_amount_arg(amount, max_value=cash)
        if val is None or val > cash:
            return await respond_safely(itx, content="❌ Invalid amount.", ephemeral=True)

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET cash=cash-?, bank=bank+? WHERE uid=?", (val, val, str(itx.user.id)))

        await respond_safely(itx, content=f"✅ Deposited {money(val)} into your bank.", ephemeral=False)

    @app_commands.command(name="withdraw", description="Withdraw bank into cash (supports 'all').")
    async def withdraw_slash(self, itx: discord.Interaction, amount: str):
        u = await db.get_user(itx.user.id)
        bank = float(u["bank"])
        val = parse_amount_arg(amount, max_value=bank)
        if val is None or val > bank:
            return await respond_safely(itx, content="❌ Invalid amount.", ephemeral=True)

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET bank=bank-?, cash=cash+? WHERE uid=?", (val, val, str(itx.user.id)))

        await respond_safely(itx, content=f"✅ Withdrew {money(val)} into your wallet.", ephemeral=False)

    @app_commands.command(name="transfer", description="Transfer bank funds (requires Bank Staff approval).")
    async def transfer_slash(self, itx: discord.Interaction, recipient: discord.Member, amount: float, note: str):
        u = await db.get_user(itx.user.id)
        bank = float(u["bank"])
        if amount <= 0 or bank < amount:
            return await respond_safely(itx, content="❌ Insufficient bank funds.", ephemeral=True)

        with db.conn:
            tx_id = db.conn.execute("""
                INSERT INTO pending_tx (sender_id, receiver_id, amount, tx_type, note)
                VALUES (?, ?, ?, 'TRANSFER', ?)
            """, (str(itx.user.id), str(recipient.id), float(amount), note)).lastrowid

        chan = itx.guild.get_channel(TRANSFER_AUTH_CHANNEL) if itx.guild else None
        if chan:
            emb = self.econ_embed(title="Bank Transfer Request")
            emb.add_field(name="From:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
            emb.add_field(name="To:", value=f"{recipient.mention} ({recipient.id})", inline=False)
            emb.add_field(name="Amount:", value=money(amount), inline=True)
            emb.add_field(name="Note:", value=note, inline=False)
            self.add_footer(emb, itx.guild)

            await chan.send(
                content=f"<@&{BANK_STAFF_ROLE_ID}>",
                embed=emb,
                view=ApprovalButtons(self, tx_id, "TRANSFER", str(itx.user.id), str(recipient.id), amount, note=note)
            )

        await respond_safely(itx, content=f"✅ Transfer #{tx_id} submitted for approval.", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Top 10 wealthiest.")
    async def leaderboard(self, itx: discord.Interaction):
        cur = db.conn.execute("SELECT uid, (cash + bank) AS total FROM users ORDER BY total DESC LIMIT 10")
        rows = cur.fetchall()

        lines = []
        for i, r in enumerate(rows, start=1):
            lines.append(f"**{i}.** <@{r['uid']}> — `{money(float(r['total']))}`")

        emb = self.econ_embed(title="Wealth Leaderboard", description="\n".join(lines) if lines else "No data.")
        self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=False)

    @app_commands.command(name="gamble", description="Gamble cash (50/50).")
    async def gamble_slash(self, itx: discord.Interaction, amount: float):
        u = await db.get_user(itx.user.id)
        cash = float(u["cash"])
        if amount <= 0 or cash < amount:
            return await respond_safely(itx, content="❌ Need more cash in wallet.", ephemeral=True)

        win = random.choice([True, False])
        async with db.lock:
            with db.conn:
                if win:
                    db.conn.execute("UPDATE users SET cash=cash+? WHERE uid=?", (amount, str(itx.user.id)))
                    await respond_safely(itx, content=f"🎲 WIN! You won **{money(amount)}**.", ephemeral=False)
                else:
                    db.conn.execute("UPDATE users SET cash=cash-? WHERE uid=?", (amount, str(itx.user.id)))
                    await respond_safely(itx, content=f"🎲 LOSS. You lost **{money(amount)}**.", ephemeral=False)

    @app_commands.command(name="inventory", description="View your inventory.")
    async def inventory_slash(self, itx: discord.Interaction):
        items = self.get_inventory(itx.user.id)
        if not items:
            return await respond_safely(itx, content="Your inventory is currently empty.", ephemeral=True)

        lines = []
        for row in items:
            item = row["item_name"]
            qty = int(row["qty"])
            ts = self.last_purchase_ts(itx.user.id, item)
            when = ts_discord(ts, "R") if ts else "N/A"
            lines.append(f"• **{item}** x{qty} — last purchase: {when}")

        emb = self.econ_embed(title=f"Inventory: {itx.user.display_name}", description="\n".join(lines))
        self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=True)

    @app_commands.command(name="shop", description="View the shop.")
    async def shop_slash(self, itx: discord.Interaction):
        emb = self.econ_embed(
            title="Server Shop",
            description=(
                f"**{SCRATCH_ITEM_NAME}** — {money(SCRATCH_PRICE)} cash\n"
                f"• Buy: `?scratchbuy` (1 per day)\n"
                f"• Use: `?scratch`"
            )
        )
        self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=True)

    @app_commands.command(name="loan_request", description="Request a loan (creates a bank staff ticket thread).")
    async def loan_request(self, itx: discord.Interaction, amount: float, reason: str):
        if amount <= 0:
            return await respond_safely(itx, content="❌ Invalid amount.", ephemeral=True)
        if not itx.guild:
            return await respond_safely(itx, content="❌ Guild required.", ephemeral=True)

        created = now_ts()
        with db.conn:
            loan_id = db.conn.execute("""
                INSERT INTO loans (borrower_id, amount, reason, created_ts)
                VALUES (?, ?, ?, ?)
            """, (str(itx.user.id), float(amount), reason, created)).lastrowid

        desk = itx.guild.get_channel(LOAN_DESK_CHANNEL_ID)
        if not desk:
            return await respond_safely(itx, content="❌ Loan desk channel not found.", ephemeral=True)

        emb = self.econ_embed(title="Loan Request Ticket")
        emb.add_field(name="Loan ID:", value=f"`{loan_id}`", inline=False)
        emb.add_field(name="Borrower:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
        emb.add_field(name="Amount:", value=money(amount), inline=True)
        emb.add_field(name="Reason:", value=reason, inline=False)
        emb.add_field(name="Requested:", value=ts_discord(created, "F"), inline=False)
        self.add_footer(emb, itx.guild)

        msg = await desk.send(content=f"<@&{BANK_STAFF_ROLE_ID}>", embed=emb)
        try:
            thread = await msg.create_thread(name=f"Loan-{loan_id} • {itx.user.display_name}", auto_archive_duration=1440)
        except Exception:
            thread = None

        with db.conn:
            tx_id = db.conn.execute("""
                INSERT INTO pending_tx (sender_id, receiver_id, amount, tx_type, note, meta)
                VALUES ('BANK', ?, ?, 'LOAN', ?, ?)
            """, (str(itx.user.id), float(amount), reason, str(loan_id))).lastrowid

        view = ApprovalButtons(self, tx_id, "LOAN", "BANK", str(itx.user.id), amount, note=reason, meta=str(loan_id))

        if thread:
            await thread.send(embed=emb, view=view)
        else:
            await desk.send(embed=emb, view=view)

        await respond_safely(itx, content="✅ Loan request submitted to Bank Staff.", ephemeral=True)

    # ---------------- Citations ----------------
    @app_commands.command(name="cite", description="LPD only: issue a citation (supervisor review).")
    @app_commands.autocomplete(penal_code=penal_autocomplete)
    async def cite_slash(
        self,
        itx: discord.Interaction,
        citizen: discord.Member,
        penal_code: str,
        amount: float,
        brief_description: str
    ):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not has_role(itx.user, LPD_ROLE_ID):
            return await respond_safely(itx, content="LPD Only.", ephemeral=True)

        if amount <= 0:
            return await respond_safely(itx, content="❌ Invalid fine amount.", ephemeral=True)

        case_code = f"LV-{random.randint(1000, 9999)}"
        created = now_ts()

        with db.conn:
            db.conn.execute("""
                INSERT INTO citations (case_code, guild_id, officer_id, citizen_id, penal_code, brief_description, amount, status, created_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?)
            """, (case_code, str(itx.guild_id), str(itx.user.id), str(citizen.id), penal_code, brief_description, float(amount), created))

        # Confirmation embed to officer
        emb = discord.Embed(title="Confirm Citation:", color=DPS_COLOR)
        emb.set_thumbnail(url=DPS_THUMBNAIL)
        emb.add_field(name="Case Code:", value=f"`{case_code}`", inline=False)
        emb.add_field(name="Officer:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
        emb.add_field(name="Citizen:", value=f"{citizen.mention} ({citizen.id})", inline=False)
        emb.add_field(name="Penal Code:", value=penal_code, inline=False)
        emb.add_field(name="Brief Description:", value=brief_description, inline=False)
        emb.add_field(name="Fine Amount:", value=money(amount), inline=True)
        emb.add_field(name="Status:", value="Pending officer confirmation.", inline=True)
        self.add_footer(emb, itx.guild)

        cog = self

        class ConfirmCiteView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=45)

            @discord.ui.button(label="Submit for Supervisor Review", style=discord.ButtonStyle.primary)
            async def submit(self, c_itx: discord.Interaction, _: discord.ui.Button):
                if c_itx.user.id != itx.user.id:
                    return await respond_safely(c_itx, content="This isn’t your citation.", ephemeral=True)

                chan = c_itx.guild.get_channel(CITATION_SUBMIT_CHANNEL)
                if not chan:
                    return await respond_safely(c_itx, content="❌ Submit channel missing.", ephemeral=True)

                # Update DB status to PENDING
                with db.conn:
                    db.conn.execute("UPDATE citations SET status='PENDING' WHERE case_code=?", (case_code,))

                # Supervisor embed MUST only include officer/citizen/fine/penal code + status
                sup = discord.Embed(title="Citation Pending Review:", color=DPS_COLOR)
                sup.set_thumbnail(url=DPS_THUMBNAIL)
                sup.add_field(name="Case Code:", value=f"`{case_code}`", inline=False)
                sup.add_field(name="Officer:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
                sup.add_field(name="Citizen:", value=f"{citizen.mention} ({citizen.id})", inline=False)
                sup.add_field(name="Fine Amount:", value=money(amount), inline=True)
                sup.add_field(name="Penal Code:", value=penal_code, inline=False)
                sup.add_field(name="Status:", value="Pending supervisor decision.", inline=False)
                cog.add_footer(sup, c_itx.guild)

                # Ping supervisor role AND ping the OFFICER who issued it
                await chan.send(
                    content=f"<@&{LPD_SUPERVISOR_ROLE_ID}> {itx.user.mention}",
                    embed=sup,
                    view=CitationActions(
                        cog,
                        case_code=case_code,
                        officer_id=itx.user.id,
                        citizen_id=citizen.id,
                        penal_code=penal_code,
                        brief_description=brief_description,
                        amount=amount
                    )
                )

                # Update officer embed status
                new_emb = emb.copy()
                # rebuild fields
                new_emb.clear_fields()
                new_emb.add_field(name="Case Code:", value=f"`{case_code}`", inline=False)
                new_emb.add_field(name="Officer:", value=f"{itx.user.mention} ({itx.user.id})", inline=False)
                new_emb.add_field(name="Citizen:", value=f"{citizen.mention} ({citizen.id})", inline=False)
                new_emb.add_field(name="Penal Code:", value=penal_code, inline=False)
                new_emb.add_field(name="Brief Description:", value=brief_description, inline=False)
                new_emb.add_field(name="Fine Amount:", value=money(amount), inline=True)
                new_emb.add_field(name="Status:", value="Submitted to supervisors.", inline=True)
                cog.add_footer(new_emb, c_itx.guild)

                await c_itx.response.edit_message(embed=new_emb, view=None)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, c_itx: discord.Interaction, _: discord.ui.Button):
                if c_itx.user.id != itx.user.id:
                    return await respond_safely(c_itx, content="This isn’t your menu.", ephemeral=True)
                with db.conn:
                    db.conn.execute("UPDATE citations SET status='CANCELLED' WHERE case_code=?", (case_code,))
                await c_itx.response.edit_message(content="Cancelled.", embed=None, view=None)

        await respond_safely(itx, embed=emb, view=ConfirmCiteView(), ephemeral=True)

    @app_commands.command(name="citation_history", description="Officers: view a citizen's approved citations.")
    async def citation_history(self, itx: discord.Interaction, citizen: discord.Member):
        if not itx.guild or not isinstance(itx.user, discord.Member) or not has_role(itx.user, LPD_ROLE_ID):
            return await respond_safely(itx, content="LPD Only.", ephemeral=True)

        cur = db.conn.execute("""
            SELECT case_code, penal_code, brief_description, amount, decided_ts, officer_id
            FROM citations
            WHERE citizen_id=? AND status='APPROVED'
            ORDER BY decided_ts DESC
            LIMIT 15
        """, (str(citizen.id),))
        rows = cur.fetchall()

        emb = discord.Embed(title=f"Citation History: {citizen.display_name}", color=DPS_COLOR)
        emb.set_thumbnail(url=DPS_THUMBNAIL)

        if not rows:
            emb.description = "No approved citations found."
            self.add_footer(emb, itx.guild)
            return await respond_safely(itx, embed=emb, ephemeral=True)

        lines = []
        for r in rows:
            when = ts_discord(int(r["decided_ts"]), "F") if r["decided_ts"] else "N/A"
            lines.append(
                f"**`{r['case_code']}`** • {money(float(r['amount']))} • {when}\n"
                f"**Penal:** {r['penal_code']}\n"
                f"**Desc:** {r['brief_description']}\n"
                f"**Officer:** <@{r['officer_id']}>\n"
            )

        emb.description = "\n".join(lines[:10])
        self.add_footer(emb, itx.guild)
        await respond_safely(itx, embed=emb, ephemeral=True)

    # ============================================================
    # PREFIX COMMANDS (ONLY in ECONOMY_PREFIX_CHANNEL_ID)
    # ============================================================

    async def ensure_prefix_channel(self, ctx: commands.Context) -> bool:
        if not ctx.guild or not ctx.channel:
            return False
        if ctx.channel.id != ECONOMY_PREFIX_CHANNEL_ID:
            try:
                await ctx.reply(f"❌ Economy prefix commands only work in <#{ECONOMY_PREFIX_CHANNEL_ID}>.", delete_after=8)
            except Exception:
                pass
            return False
        return True

    @commands.command(name="balance")
    async def p_balance(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        if not await self.ensure_prefix_channel(ctx):
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
        if not await self.ensure_prefix_channel(ctx):
            return
        u = await db.get_user(ctx.author.id)
        cash = float(u["cash"])
        val = parse_amount_arg(amount, max_value=cash)
        if val is None or val > cash:
            return await ctx.send("❌ Invalid amount. Use `?deposit all` or `?deposit 6,835`.")

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET cash=cash-?, bank=bank+? WHERE uid=?", (val, val, str(ctx.author.id)))

        await ctx.send(f"✅ Deposited {money(val)}.")

    @commands.command(name="withdraw")
    async def p_withdraw(self, ctx: commands.Context, amount: str):
        if not await self.ensure_prefix_channel(ctx):
            return
        u = await db.get_user(ctx.author.id)
        bank = float(u["bank"])
        val = parse_amount_arg(amount, max_value=bank)
        if val is None or val > bank:
            return await ctx.send("❌ Invalid amount. Use `?withdraw all` or `?withdraw 6,835`.")

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET bank=bank-?, cash=cash+? WHERE uid=?", (val, val, str(ctx.author.id)))

        await ctx.send(f"✅ Withdrew {money(val)}.")

    @commands.command(name="gamble")
    async def p_gamble(self, ctx: commands.Context, amount: str):
        if not await self.ensure_prefix_channel(ctx):
            return
        u = await db.get_user(ctx.author.id)
        cash = float(u["cash"])
        val = parse_amount_arg(amount, max_value=cash)
        if val is None or val > cash:
            return await ctx.send("❌ Invalid amount. Use `?gamble 500` or `?gamble 6,835`.")

        win = random.choice([True, False])
        async with db.lock:
            with db.conn:
                if win:
                    db.conn.execute("UPDATE users SET cash=cash+? WHERE uid=?", (val, str(ctx.author.id)))
                    await ctx.send(f"🎲 WIN! You won **{money(val)}**.")
                else:
                    db.conn.execute("UPDATE users SET cash=cash-? WHERE uid=?", (val, str(ctx.author.id)))
                    await ctx.send(f"🎲 LOSS. You lost **{money(val)}**.")

    @commands.command(name="scratchbuy")
    async def p_scratchbuy(self, ctx: commands.Context):
        if not await self.ensure_prefix_channel(ctx):
            return

        u = await db.get_user(ctx.author.id)
        cash = float(u["cash"])
        if cash < SCRATCH_PRICE:
            return await ctx.send(f"❌ You need {money(SCRATCH_PRICE)} cash to buy a scratch card.")

        today = datetime.now(timezone.utc).date().isoformat()
        row = db.conn.execute("SELECT last_buy_date FROM scratch_daily WHERE uid=?", (str(ctx.author.id),)).fetchone()
        if row and row["last_buy_date"] == today:
            return await ctx.send("❌ You already bought your daily scratch card today.")

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE users SET cash=cash-? WHERE uid=?", (SCRATCH_PRICE, str(ctx.author.id)))
                self.add_inventory_item(ctx.author.id, SCRATCH_ITEM_NAME, 1)
                db.conn.execute("INSERT OR REPLACE INTO scratch_daily (uid, last_buy_date) VALUES (?, ?)", (str(ctx.author.id), today))

        await ctx.send(f"✅ Purchased **{SCRATCH_ITEM_NAME}** for {money(SCRATCH_PRICE)}. Use `?scratch`!")

    @commands.command(name="scratch")
    async def p_scratch(self, ctx: commands.Context):
        if not await self.ensure_prefix_channel(ctx):
            return

        row = db.conn.execute("SELECT qty FROM inventory WHERE uid=? AND item_name=?", (str(ctx.author.id), SCRATCH_ITEM_NAME)).fetchone()
        qty = int(row["qty"]) if row else 0
        if qty <= 0:
            return await ctx.send("❌ You don’t have a scratch card. Buy one with `?scratchbuy` (1/day).")

        roll = random.random()
        if roll < 0.60:
            prize = 0
        elif roll < 0.90:
            prize = random.choice([50, 75, 100, 150, 200])
        elif roll < 0.985:
            prize = random.choice([500, 750, 1000, 1500, 2000])
        else:
            prize = random.choice([5000, 7500, 10000])

        symbols = ["🍒", "🍋", "⭐", "💎", "🍀", "7️⃣"]
        board = [random.choice(symbols) for _ in range(9)]
        grid = "\n".join([" ".join(board[i:i+3]) for i in range(0, 9, 3)])

        async with db.lock:
            with db.conn:
                db.conn.execute("UPDATE inventory SET qty = qty - 1 WHERE uid=? AND item_name=?",
                                (str(ctx.author.id), SCRATCH_ITEM_NAME))
                if prize > 0:
                    db.conn.execute("UPDATE users SET cash=cash+? WHERE uid=?", (float(prize), str(ctx.author.id)))

        if prize > 0:
            await ctx.send(f"🧾 **Scratch Result**\n```{grid}```\n🎉 You won **{money(prize)}** cash!")
        else:
            await ctx.send(f"🧾 **Scratch Result**\n```{grid}```\n😬 No win this time.")

    # ============================================================
    # SHIFT SYSTEM
    # ============================================================

    @tasks.loop(minutes=1)
    async def salary_task(self):
        guild = self.bot.get_guild(MAIN_GUILD_ID)
        if not guild:
            return

        now = now_ts()

        async with db.lock:
            for m in guild.members:
                if not m.voice or not m.voice.channel or not m.voice.channel.category:
                    continue
                if m.voice.channel.category.id != SALARY_VC_CATEGORY_ID:
                    continue

                inactive = bool(m.voice.self_deaf or m.voice.self_mute or m.voice.channel.id == AFK_CHANNEL_ID)
                if inactive:
                    continue

                rate, dept = await self.get_pay_rate_and_dept(m)

                existing = db.conn.execute("SELECT uid FROM active_shifts WHERE uid=?", (str(m.id),)).fetchone()
                if not existing:
                    with db.conn:
                        db.conn.execute("""
                            INSERT INTO active_shifts (uid, minutes, gross, start_ts, last_seen_ts, afk_timer)
                            VALUES (?, 1, ?, ?, ?, 0)
                        """, (str(m.id), float(rate), now, now))
                else:
                    with db.conn:
                        db.conn.execute("""
                            UPDATE active_shifts
                            SET minutes = minutes + 1,
                                gross = gross + ?,
                                last_seen_ts = ?
                            WHERE uid = ?
                        """, (float(rate), now, str(m.id)))

    @tasks.loop(seconds=60)
    async def cleanup_task(self):
        guild = self.bot.get_guild(MAIN_GUILD_ID)
        if not guild:
            return

        now = now_ts()
        cutoff = now - 180

        async with db.lock:
            rows = db.conn.execute("SELECT * FROM active_shifts").fetchall()
            for row in rows:
                last_seen = int(row["last_seen_ts"] or 0)
                if last_seen >= cutoff:
                    continue

                uid = int(row["uid"])
                minutes = int(row["minutes"])
                gross = float(row["gross"])
                start_ts = int(row["start_ts"] or 0)
                end_ts = now

                member = guild.get_member(uid)
                if not member:
                    with db.conn:
                        db.conn.execute("DELETE FROM active_shifts WHERE uid=?", (str(uid),))
                    continue

                rate, dept = await self.get_pay_rate_and_dept(member)

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

                meta = f"{start_ts}|{end_ts}|{minutes}|{rate}|{dept}"

                with db.conn:
                    tx_id = db.conn.execute("""
                        INSERT INTO pending_tx (sender_id, receiver_id, amount, tx_type, meta)
                        VALUES ('GOV', ?, ?, ?, ?)
                    """, (str(uid), gross, tx_type, meta)).lastrowid
                    db.conn.execute("DELETE FROM active_shifts WHERE uid=?", (str(uid),))

                chan = guild.get_channel(auth_channel_id)
                if chan:
                    emb = self.econ_embed(title=f"{dept} Shift Completed")
                    emb.add_field(name="Employee:", value=f"{member.mention} ({member.id})", inline=False)
                    emb.add_field(name="Shift Start:", value=ts_discord(start_ts, "F") if start_ts else "N/A", inline=False)
                    emb.add_field(name="Shift End:", value=ts_discord(end_ts, "F"), inline=False)
                    emb.add_field(name="Minutes:", value=str(minutes), inline=True)
                    emb.add_field(name="Rate (per minute):", value=money(rate), inline=True)
                    emb.add_field(name="Pay:", value=money(gross), inline=False)
                    self.add_footer(emb, guild)

                    await chan.send(
                        content=f"<@&{ping_role}>",
                        embed=emb,
                        view=ApprovalButtons(self, tx_id, tx_type, "GOV", str(uid), gross, meta=meta)
                    )

    # ============================================================
    # ADMIN MONEY
    # ============================================================

    @app_commands.command(name="addmoney", description="Admin: add money to bank.")
    @app_commands.checks.has_permissions(administrator=True)
    async def addmoney(self, itx: discord.Interaction, target: discord.Member, amount: float):
        with db.conn:
            db.conn.execute("UPDATE users SET bank=bank+? WHERE uid=?", (float(amount), str(target.id)))
        await respond_safely(itx, content=f"✅ Added {money(amount)} to {target.mention}.", ephemeral=True)

    @app_commands.command(name="removemoney", description="Admin: remove money from bank.")
    @app_commands.checks.has_permissions(administrator=True)
    async def removemoney(self, itx: discord.Interaction, target: discord.Member, amount: float):
        with db.conn:
            db.conn.execute("UPDATE users SET bank=bank-? WHERE uid=?", (float(amount), str(target.id)))
        await respond_safely(itx, content=f"✅ Removed {money(amount)} from {target.mention}.", ephemeral=True)

# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
