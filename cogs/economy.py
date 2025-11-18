import discord
from discord.ext import commands
import json
import time
import re

WHITELIST_FILE = "whitelisted.json"
SHIFT_FILE = "shifts.json"

CALLSIGN_REGEX = r"\b\d{2,4}\b"  # Example: 201, 1023, etc.
TRACKED_CATEGORY_IDS = [1436503704143396914]  # put your category IDs here


def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


class Shifts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------
    # Helpers
    # ---------------------------

    def has_callsign(self, member: discord.Member):
        if not member.nick:
            return False
        return bool(re.search(CALLSIGN_REGEX, member.nick))

    def in_tracked_vc(self, member: discord.Member):
        if not member.voice:
            return False
        if not member.voice.channel:
            return False
        if not member.voice.channel.category:
            return False
        return member.voice.channel.category.id in TRACKED_CATEGORY_IDS

    # ---------------------------
    # WHITELIST COMMANDS
    # ---------------------------

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def whitelist_add(self, ctx, member: discord.Member):
        data = load_json(WHITELIST_FILE)

        if member.id in data.get("whitelisted", []):
            return await ctx.reply(f"{member.mention} is already whitelisted.")

        data.setdefault("whitelisted", []).append(member.id)
        save_json(WHITELIST_FILE, data)

        await ctx.reply(f"Added {member.mention} to whitelist.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def whitelist_remove(self, ctx, member: discord.Member):
        data = load_json(WHITELIST_FILE)

        if member.id not in data.get("whitelisted", []):
            return await ctx.reply(f"{member.mention} is not whitelisted.")

        data["whitelisted"].remove(member.id)
        save_json(WHITELIST_FILE, data)

        await ctx.reply(f"Removed {member.mention} from whitelist.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def whitelist_list(self, ctx):
        data = load_json(WHITELIST_FILE)
        wl = data.get("whitelisted", [])

        if not wl:
            return await ctx.reply("No whitelisted users.")

        users = "\n".join([f"<@{uid}>" for uid in wl])
        await ctx.reply(users)

    # ---------------------------
    # SHIFT TRACKING
    # ---------------------------

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        shift_data = load_json(SHIFT_FILE)
        user = str(member.id)

        # Initialize user entry
        if user not in shift_data.get("shifts", {}):
            shift_data.setdefault("shifts", {})[user] = {
                "active": False,
                "start": None,
                "total_seconds": 0
            }

        user_data = shift_data["shifts"][user]

        is_valid = self.has_callsign(member) and self.in_tracked_vc(member)

        # START SHIFT
        if is_valid and not user_data["active"]:
            user_data["active"] = True
            user_data["start"] = time.time()
            save_json(SHIFT_FILE, shift_data)
            return

        # END SHIFT
        if not is_valid and user_data["active"]:
            duration = time.time() - user_data["start"]
            user_data["total_seconds"] += int(duration)
            user_data["active"] = False
            user_data["start"] = None
            save_json(SHIFT_FILE, shift_data)
            return


async def setup(bot):
    await bot.add_cog(Shifts(bot))
