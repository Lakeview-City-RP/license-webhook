# cogs/blackmarket.py
from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import asyncio
import random
from datetime import datetime, timezone

# -----------------------
# CONFIG
# -----------------------
GUILD_ID = 1328475009542258688
DB_NAME = "lakeview_shadow.db"  # same DB your economy uses

BLACKMARKET_CHANNEL_ID = 1455026585408372787        # <-- set this (announce/open/close)
BLACKMARKET_LOG_CHANNEL_ID = 1455026755818487838    # <-- set this (purchase logs)

BM_OPEN_PING_ROLE_ID = 1436150194726113330  # <-- ping this role when BM opens
BM_START_ROLE_ID = 1328939648621346848      # <-- required role to start/end BM (admins bypass)

BM_WALLET = "bank"  # "bank" or "cash"

BM_COLOR = 0x757575
BM_THUMBNAIL = (
    "https://media.discordapp.net/attachments/1377401295220117746/"
    "1437245076945375393/WHITELISTED_NO_BACKGROUND.png?format=webp&quality=lossless"
)

# RP-safe item role names (bot will create these roles and assign them)
BM_ITEMS = [
{"id": "REG_SIDEARM_A", "name": "Beretta M9", "category": "Registered", "min_price": 800, "max_price": 1200, "stock": (2, 6), "limit": 1},
    {"id": "REG_SIDEARM_B", "name": "Desert Eagle", "category": "Registered", "min_price": 900, "max_price": 1400, "stock": (2, 6), "limit": 1},
    {"id": "REG_PISTOL_C",  "name": "Colt M1911", "category": "Registered", "min_price": 750, "max_price": 1150, "stock": (2, 6), "limit": 1},
    {"id": "REG_REVOLVER",  "name": "Colt Python", "category": "Registered", "min_price": 850, "max_price": 1300, "stock": (2, 6), "limit": 1},
    {"id": "REG_ANTIQUE",   "name": "Lemat Revolver", "category": "Registered", "min_price": 700, "max_price": 1100, "stock": (1, 4), "limit": 1},

    # Contraband (“illegal vibe”)
    {"id": "CON_LMG",       "name": "M249", "category": "Contraband", "min_price": 4500, "max_price": 6500, "stock": (1, 2), "limit": 1},
    {"id": "CON_LRR",       "name": "Remington MSR", "category": "Contraband", "min_price": 4000, "max_price": 6200, "stock": (1, 2), "limit": 1},
    {"id": "CON_BR",        "name": "M14", "category": "Contraband", "min_price": 3200, "max_price": 5200, "stock": (1, 3), "limit": 1},
    {"id": "CON_AR",        "name": "AK47", "category": "Contraband", "min_price": 2800, "max_price": 4800, "stock": (1, 3), "limit": 1},
    {"id": "CON_VSMG",      "name": "PPSH 41", "category": "Contraband", "min_price": 2400, "max_price": 4200, "stock": (1, 3), "limit": 1},
    {"id": "CON_MSMG",      "name": "Kriss Vector", "category": "Contraband", "min_price": 2600, "max_price": 4400, "stock": (1, 3), "limit": 1},
    {"id": "CON_DMR",       "name": "LMT L129A1", "category": "Contraband", "min_price": 3000, "max_price": 5000, "stock": (1, 2), "limit": 1},
    {"id": "CON_CSMG",      "name": "Skorpion", "category": "Contraband", "min_price": 2200, "max_price": 3800, "stock": (1, 3), "limit": 1},
    {"id": "CON_MP",        "name": "TEC 9", "category": "Contraband", "min_price": 1800, "max_price": 3200, "stock": (1, 4), "limit": 1},
    {"id": "CON_TSHOT",     "name": "Remington 870", "category": "Contraband", "min_price": 2000, "max_price": 3600, "stock": (1, 3), "limit": 1},
]

def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())

def ts_discord(ts: int) -> str:
    return f"<t:{ts}:F>"

# -----------------------
# DB
# -----------------------
class BMDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = asyncio.Lock()
        self._init_tables()

    def _init_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bm_state (
                    guild_id TEXT PRIMARY KEY,
                    is_open INTEGER NOT NULL DEFAULT 0,
                    closes_ts INTEGER NOT NULL DEFAULT 0,
                    market_id INTEGER NOT NULL DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bm_inventory (
                    guild_id TEXT NOT NULL,
                    market_id INTEGER NOT NULL,
                    item_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    stock INTEGER NOT NULL,
                    per_user_limit INTEGER NOT NULL,
                    PRIMARY KEY(guild_id, market_id, item_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bm_receipts (
                    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    market_id INTEGER NOT NULL,
                    buyer_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    total_price INTEGER NOT NULL,
                    created_ts INTEGER NOT NULL
                )
            """)

bmdb = BMDB()

# -----------------------
# LOG BUTTON VIEW
# -----------------------
class ViewBuyerInventory(discord.ui.View):
    def __init__(self, cog: "BlackMarketCog", buyer_id: int):
        super().__init__(timeout=3600)
        self.cog = cog
        self.buyer_id = buyer_id

    @discord.ui.button(label="View Inventory", style=discord.ButtonStyle.secondary)
    async def view_inventory(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not self.cog._can_staff(itx.user):
            return await itx.response.send_message("Staff only.", ephemeral=True)

        self.cog._ensure_inventory_qty()


        rows = bmdb.conn.execute(
            "SELECT item_name, qty FROM inventory WHERE uid = ? ORDER BY item_name ASC",
            (str(self.buyer_id),)
        ).fetchall()

        member = itx.guild.get_member(self.buyer_id) if itx.guild else None
        who = member.mention if member else f"`{self.buyer_id}`"

        if not rows:
            emb = self.cog._embed(title="User Inventory", description=f"{who} has no items.")
            return await itx.response.send_message(embed=emb, ephemeral=True)

        lines = [f"• **{r['item_name']}** × `{int(r['qty'])}`" for r in rows[:40]]
        emb = self.cog._embed(title="User Inventory", description=f"{who}\n\n" + "\n".join(lines))
        await itx.response.send_message(embed=emb, ephemeral=True)




# -----------------------
# UI
# -----------------------
class BuyConfirmView(discord.ui.View):
    def __init__(self, cog: "BlackMarketCog", item: sqlite3.Row, buyer_id: int):
        super().__init__(timeout=45)
        self.cog = cog
        self.item = item
        self.buyer_id = buyer_id
        self.qty = 1

    @discord.ui.button(label="Qty: 1", style=discord.ButtonStyle.secondary)
    async def qty_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id != self.buyer_id:
            return await itx.response.send_message("This isn’t your menu.", ephemeral=True)
        self.qty = 2 if self.qty == 1 else 1
        btn.label = f"Qty: {self.qty}"
        await itx.response.edit_message(view=self)

    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success)
    async def confirm(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id != self.buyer_id:
            return await itx.response.send_message("This isn’t your menu.", ephemeral=True)
        await self.cog._purchase(itx, self.item["item_id"], self.qty)

@discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
async def cancel(self, itx: discord.Interaction, btn: discord.ui.Button):
    if itx.user.id != self.buyer_id:
        return await itx.response.send_message("This isn’t your menu.", ephemeral=True)

    await itx.response.edit_message(content="Cancelled.", embed=None, view=None)


class MarketSelect(discord.ui.Select):
    def __init__(self, cog: "BlackMarketCog", rows: list[sqlite3.Row], buyer_id: int):
        self.cog = cog
        self.rows = {r["item_id"]: r for r in rows}
        self.buyer_id = buyer_id

        options = []
        for r in rows[:25]:
            label = r["display_name"][:100]
            desc = f'{r["category"]} • ${r["price"]:,} • Stock {r["stock"]}'
            options.append(discord.SelectOption(label=label, description=desc[:100], value=r["item_id"]))

        super().__init__(placeholder="Select an item…", options=options)

    async def callback(self, itx: discord.Interaction):
        if itx.user.id != self.buyer_id:
            return await itx.response.send_message("This isn’t your menu.", ephemeral=True)

        item = self.rows[self.values[0]]
        emb = self.cog._embed(
            title="Black Market Purchase",
            description=(
                f"**Item:** {item['display_name']}\n"
                f"**Category:** {item['category']}\n"
                f"**Price:** ${item['price']:,}\n"
                f"**Stock:** {item['stock']}\n"
                f"**Limit:** {item['per_user_limit']} per market"
            )
        )
        await itx.response.edit_message(embed=emb, view=BuyConfirmView(self.cog, item, itx.user.id))

class MarketView(discord.ui.View):
    def __init__(self, cog: "BlackMarketCog", rows: list[sqlite3.Row], buyer_id: int):
        super().__init__(timeout=60)
        self.add_item(MarketSelect(cog, rows, buyer_id))

# -----------------------
# COG
# -----------------------
class BlackMarketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ensure_inventory_qty()
        self.auto_close_task.start()

    def _can_start_bm(self, member: discord.Member) -> bool:
        return member.guild_permissions.administrator or any(r.id == BM_START_ROLE_ID for r in member.roles)

    def _can_staff(self, member: discord.Member) -> bool:
        return self._can_start_bm(member)

    def _embed(self, *, title: str, description: str) -> discord.Embed:
        emb = discord.Embed(title=title, description=description, color=BM_COLOR)
        emb.set_thumbnail(url=BM_THUMBNAIL)
        return emb

    def _ensure_inventory_qty(self):
        # Ensure inventory exists + has qty column
        info = bmdb.conn.execute("PRAGMA table_info(inventory)").fetchall()

        if not info:
            with bmdb.conn:
                bmdb.conn.execute("""
                    CREATE TABLE IF NOT EXISTS inventory (
                        uid TEXT NOT NULL,
                        item_name TEXT NOT NULL,
                        qty INTEGER NOT NULL DEFAULT 1,
                        PRIMARY KEY(uid, item_name)
                    )
                """)
            return

        cols = [r["name"] for r in info]
        if "qty" not in cols:
            with bmdb.conn:
                bmdb.conn.execute("ALTER TABLE inventory ADD COLUMN qty INTEGER NOT NULL DEFAULT 1")
            print("Added qty column to inventory table.")

    async def _get_state(self, guild_id: int) -> sqlite3.Row:
        row = bmdb.conn.execute("SELECT * FROM bm_state WHERE guild_id = ?", (str(guild_id),)).fetchone()
        if not row:
            with bmdb.conn:
                bmdb.conn.execute(
                    "INSERT INTO bm_state (guild_id, is_open, closes_ts, market_id) VALUES (?, 0, 0, 0)",
                    (str(guild_id),)
                )
            row = bmdb.conn.execute("SELECT * FROM bm_state WHERE guild_id = ?", (str(guild_id),)).fetchone()
        return row

    async def _ensure_role(self, guild: discord.Guild, role_name: str) -> discord.Role:
        existing = discord.utils.get(guild.roles, name=role_name)
        if existing:
            return existing
        return await guild.create_role(name=role_name, reason="Black Market purchase")

    async def _add_to_inventory(self, uid: int, item_name: str, qty: int):
        self._ensure_inventory_qty()
        with bmdb.conn:
            cur = bmdb.conn.execute(
                "UPDATE inventory SET qty = qty + ? WHERE uid = ? AND item_name = ?",
                (int(qty), str(uid), item_name)
            )
            if cur.rowcount == 0:
                bmdb.conn.execute(
                    "INSERT INTO inventory (uid, item_name, qty) VALUES (?, ?, ?)",
                    (str(uid), item_name, int(qty))
                )

    # ✅ THIS IS THE METHOD YOU WERE MISSING (and it is INSIDE the class)
    async def _open_market(self, guild: discord.Guild, duration_minutes: int):
        start = now_ts()
        closes = start + (duration_minutes * 60)

        async with bmdb.lock:
            state = await self._get_state(guild.id)
            new_market_id = int(state["market_id"]) + 1

            with bmdb.conn:
                bmdb.conn.execute(
                    "UPDATE bm_state SET is_open = 1, closes_ts = ?, market_id = ? WHERE guild_id = ?",
                    (closes, new_market_id, str(guild.id))
                )
                bmdb.conn.execute("DELETE FROM bm_inventory WHERE guild_id = ?", (str(guild.id),))

                for item in BM_ITEMS:
                    price = random.randint(item["min_price"], item["max_price"])
                    stock = random.randint(item["stock"][0], item["stock"][1])
                    bmdb.conn.execute(
                        "INSERT INTO bm_inventory (guild_id, market_id, item_id, display_name, category, price, stock, per_user_limit) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(guild.id), new_market_id, item["id"], item["name"], item["category"], price, stock, item["limit"])
                    )

        chan = guild.get_channel(BLACKMARKET_CHANNEL_ID)
        if not chan:
            return

        emb = self._embed(
            title="Whitelisted Black Market Event: Market Online!",
            description=(
                f"> The **Black Market** is now open for roleplay item purchases.\n"
                f"> **Closes:** {ts_discord(closes)}\n\n"
                f"Use ``/blackmarket`` to view inventory and purchase an item."
            )
        )
        icon_url = guild.icon.url if guild.icon else None
        emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)

        await chan.send(content=f"<@&{BM_OPEN_PING_ROLE_ID}>", embed=emb)

    async def _close_market(self, guild: discord.Guild, *, reason: str = "Closed"):
        async with bmdb.lock:
            with bmdb.conn:
                bmdb.conn.execute(
                    "UPDATE bm_state SET is_open = 0, closes_ts = 0 WHERE guild_id = ?",
                    (str(guild.id),)
                )

        chan = guild.get_channel(BLACKMARKET_CHANNEL_ID)
        if chan:
            emb = self._embed(title="Black Market CLOSED", description=reason)
            icon_url = guild.icon.url if guild.icon else None
            emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
            await chan.send(embed=emb)

    async def _purchase(self, itx: discord.Interaction, item_id: str, qty: int):
        guild = itx.guild
        if not guild:
            return await itx.response.edit_message(content="Guild only.", embed=None, view=None)

        async with bmdb.lock:
            state = await self._get_state(guild.id)
            if not int(state["is_open"]):
                return await itx.response.edit_message(content="Market is closed.", embed=None, view=None)

            closes = int(state["closes_ts"])
            if now_ts() >= closes:
                await self._close_market(guild, reason="Market time expired.")
                return await itx.response.edit_message(content="Market just closed.", embed=None, view=None)

            market_id = int(state["market_id"])
            item = bmdb.conn.execute(
                "SELECT * FROM bm_inventory WHERE guild_id = ? AND market_id = ? AND item_id = ?",
                (str(guild.id), market_id, item_id)
            ).fetchone()

            if not item:
                return await itx.response.edit_message(content="Item not found.", embed=None, view=None)
            if int(item["stock"]) <= 0:
                return await itx.response.edit_message(content="Sold out.", embed=None, view=None)

            qty = max(1, int(qty))
            qty = min(qty, int(item["stock"]))

            bought = bmdb.conn.execute(
                "SELECT COALESCE(SUM(qty), 0) AS q FROM bm_receipts "
                "WHERE guild_id = ? AND market_id = ? AND buyer_id = ? AND item_id = ?",
                (str(guild.id), market_id, str(itx.user.id), item_id)
            ).fetchone()["q"]

            if int(bought) + qty > int(item["per_user_limit"]):
                return await itx.response.edit_message(
                    content=f"Limit reached (max {item['per_user_limit']} per market).",
                    embed=None,
                    view=None
                )

            total = int(item["price"]) * qty

            # Ensure economy user row exists
            u = bmdb.conn.execute("SELECT * FROM users WHERE uid = ?", (str(itx.user.id),)).fetchone()
            if not u:
                with bmdb.conn:
                    bmdb.conn.execute("INSERT INTO users (uid, cash, bank) VALUES (?, 0, 5000)", (str(itx.user.id),))
                u = bmdb.conn.execute("SELECT * FROM users WHERE uid = ?", (str(itx.user.id),)).fetchone()

            wallet_amt = float(u[BM_WALLET])
            if wallet_amt < total:
                return await itx.response.edit_message(content="Insufficient funds.", embed=None, view=None)

            with bmdb.conn:
                bmdb.conn.execute(
                    f"UPDATE users SET {BM_WALLET} = {BM_WALLET} - ? WHERE uid = ?",
                    (total, str(itx.user.id))
                )
                bmdb.conn.execute(
                    "UPDATE bm_inventory SET stock = stock - ? WHERE guild_id = ? AND market_id = ? AND item_id = ?",
                    (qty, str(guild.id), market_id, item_id)
                )
                receipt_id = bmdb.conn.execute(
                    "INSERT INTO bm_receipts (guild_id, market_id, buyer_id, item_id, display_name, qty, total_price, created_ts) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(guild.id), market_id, str(itx.user.id), item_id, item["display_name"], qty, total, now_ts())
                ).lastrowid

            await self._add_to_inventory(itx.user.id, item["display_name"], qty)

            # role grant
            try:
                role = await self._ensure_role(guild, item["display_name"])
                member = guild.get_member(itx.user.id)
                if member and role not in member.roles:
                    await member.add_roles(role, reason="Black Market purchase")
            except discord.Forbidden:
                return await itx.response.edit_message(
                    content="I need **Manage Roles** and my bot role must be above the roles I create.",
                    embed=None,
                    view=None
                )

            emb = self._embed(
                title="Whitelisted: Purchase Complete",
                description=(
                    f"**Role Granted:** {item['display_name']}\n"
                    f"**Qty:** {qty}\n"
                    f"**Total:** ${total:,}\n"
                    f"**Receipt:** `{receipt_id}`\n"
                    f"**Market Closes:** {ts_discord(closes)}"
                )
            )
            icon_url = guild.icon.url if guild.icon else None
            emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)

            await itx.response.edit_message(embed=emb, view=None, content=None)

            logc = guild.get_channel(BLACKMARKET_LOG_CHANNEL_ID)
            if logc:
                log_emb = self._embed(
                    title="Black Market Sale",
                    description=(
                        f"**Buyer:** {itx.user.mention} (`{itx.user.id}`)\n"
                        f"**Item:** {item['display_name']}\n"
                        f"**Qty:** {qty}\n"
                        f"**Total:** ${total:,}\n"
                        f"**Receipt:** `{receipt_id}`"
                    )
                )
                icon_url = guild.icon.url if guild.icon else None
                log_emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
                await logc.send(embed=log_emb, view=ViewBuyerInventory(self, itx.user.id))

    # -----------------------
    # Commands
    # -----------------------
    @app_commands.command(name="bm_forcespawn", description="Force open the Black Market now")
    async def bm_forcespawn(self, itx: discord.Interaction, duration_minutes: app_commands.Range[int, 5, 180] = 60):
        if not itx.guild:
            return await itx.response.send_message("Guild only.", ephemeral=True)
        if not self._can_start_bm(itx.user):
            return await itx.response.send_message("You do not have permission to start the Black Market.", ephemeral=True)

        await self._open_market(itx.guild, duration_minutes)
        await itx.response.send_message(f"Black Market opened for **{duration_minutes} minutes**.", ephemeral=True)

    @app_commands.command(name="bm_forceend", description="Force end the Black Market now")
    async def bm_forceend(self, itx: discord.Interaction):
        if not itx.guild:
            return await itx.response.send_message("Guild only.", ephemeral=True)
        if not self._can_start_bm(itx.user):
            return await itx.response.send_message("You do not have permission to end the Black Market.", ephemeral=True)

        await self._close_market(itx.guild, reason="LKVC Whitelisted: Black Market.")
        await itx.response.send_message("Black Market force-ended.", ephemeral=True)

    @app_commands.command(name="blackmarket", description="Browse the Black Market (only when open)")
    async def blackmarket(self, itx: discord.Interaction):
        if not itx.guild:
            return await itx.response.send_message("Guild only.", ephemeral=True)

        # Acknowledge fast to avoid Unknown interaction on slower runs
        try:
            await itx.response.defer(ephemeral=True)
        except (discord.NotFound, discord.InteractionResponded):
            return

        state = await self._get_state(itx.guild.id)
        if not int(state["is_open"]):
            emb = self._embed(title="Black Market", description="Not open right now.")
            icon_url = itx.guild.icon.url if itx.guild.icon else None
            emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
            return await itx.followup.send(embed=emb, ephemeral=True)

        closes = int(state["closes_ts"])
        if now_ts() >= closes:
            await self._close_market(itx.guild, reason="Market time expired.")
            emb = self._embed(title="Black Market", description="Not open right now.")
            icon_url = itx.guild.icon.url if itx.guild.icon else None
            emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
            return await itx.followup.send(embed=emb, ephemeral=True)

        market_id = int(state["market_id"])
        rows = bmdb.conn.execute(
            "SELECT * FROM bm_inventory WHERE guild_id = ? AND market_id = ? AND stock > 0 ORDER BY category, price DESC",
            (str(itx.guild.id), market_id)
        ).fetchall()

        if not rows:
            emb = self._embed(title="Black Market", description="Everything is sold out.")
            icon_url = itx.guild.icon.url if itx.guild.icon else None
            emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)
            return await itx.followup.send(embed=emb, ephemeral=True)

        emb = self._embed(
            title="🕶️ Black Market Inventory",
            description=f"Closes at {ts_discord(closes)}.\nSelect an item below to buy."
        )
        icon_url = itx.guild.icon.url if itx.guild.icon else None
        emb.set_footer(text="Lakeview City Whitelisted - Automated Systems", icon_url=icon_url)

        await itx.followup.send(embed=emb, view=MarketView(self, rows, itx.user.id), ephemeral=True)

    @tasks.loop(seconds=15)
    async def auto_close_task(self):
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        state = await self._get_state(guild.id)
        if not int(state["is_open"]):
            return

        closes = int(state["closes_ts"])
        if closes and now_ts() >= closes:
            await self._close_market(guild, reason="Market time expired.")

async def setup(bot: commands.Bot):
    await bot.add_cog(BlackMarketCog(bot))
