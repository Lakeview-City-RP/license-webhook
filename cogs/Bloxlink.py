# cogs/bloxlink.py

import discord
from discord.ext import commands
import aiohttp
import asyncio

# Import the API Key AND the Guild ID (We keep GUILD_ID in case we need it later)
from config import BLOXLINK_KEY, GUILD_ID

# --- FIX: Reverting to the V4 GLOBAL endpoint structure ---
# This general V4 endpoint works best with the 'Authorization' header.
BLOXLINK_API_URL_BASE = "https://api.blox.link/v4/public/discord/"


class Bloxlink(commands.Cog):
    # ... __init__ and cog_unload methods remain the same ...

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def _fetch_bloxlink_data(self, user_id: int) -> dict:
        """
        Fetches the verification status from Bloxlink using the V4 Global API structure.
        """

        # 1. Define the necessary headers, using 'Authorization' for V4
        headers = {
            "Authorization": BLOXLINK_KEY,  # <-- Standard V4 Header
            "Accept": "application/json"
        }

        # 2. Construct the URL using the V4 Global format
        url = f"{BLOXLINK_API_URL_BASE}{user_id}"

        async with self.session.get(url, headers=headers) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                if response.status == 200:
                    return {"status": "error", "message": "Received HTTP 200 but response was empty/malformed."}
                else:
                    return {"status": "error",
                            "message": f"Non-JSON response (Status: {response.status}). The API server likely had an internal error."}

            # 3. Handle V4 responses
            if response.status == 200:
                return data
            elif response.status == 404:
                # 404: User is not verified
                return {"status": "error", "message": "User is not verified with Bloxlink (Status 404)."}
            elif response.status == 401:
                # 401: API Key is invalid or missing
                return {"status": "error", "message": "Invalid Bloxlink API Key (Status 401). Using V4 structure."}
            else:
                api_msg = data.get("message", "No message provided.")
                return {"status": "error", "message": f"API returned status {response.status}. Message: {api_msg}"}

    # The rest of the Bloxlink class remains unchanged...
    @commands.command(name="blxtest", aliases=["blxcheck", "bloxlink"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def bloxlink_test(self, ctx: commands.Context, user: discord.User = None):
        if user is None:
            user = ctx.author

        target_id = user.id

        await ctx.typing()

        data = await self._fetch_bloxlink_data(target_id)

        embed = discord.Embed(
            title=f"Bloxlink Verification Check for {user.display_name}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        status = data.get("status")

        if status == "ok":
            roblox_username = data.get("cachedUsername", "N/A")
            roblox_id = data.get("robloxId", "N/A")

            embed.color = discord.Color.green()
            embed.add_field(name="Verification Status", value="✅ **Verified**", inline=False)
            embed.add_field(name="Roblox Username",
                            value=f"[{roblox_username}](https://www.roblox.com/users/{roblox_id}/profile)", inline=True)
            embed.add_field(name="Roblox ID", value=f"`{roblox_id}`", inline=True)

        elif status == "error" and "not verified" in data.get("message", "").lower():
            embed.color = discord.Color.yellow()
            embed.add_field(name="Verification Status", value="⚠️ **Not Verified**", inline=False)
            embed.add_field(name="User Action", value="This user is not linked via Bloxlink.", inline=False)

        else:
            embed.color = discord.Color.red()
            embed.add_field(name="Status", value="❌ **Lookup Failed**", inline=False)
            embed.add_field(name="Details", value=f"API Message: {data.get('message', 'Unknown error.')}", inline=False)

        await ctx.send(embed=embed)

    @bloxlink_test.error
    async def bloxlink_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.UserNotFound):
            await ctx.send("❌ Could not find that user or ID.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ This command is on cooldown. Try again in **{error.retry_after:.2f}s**.", ephemeral=True)
        else:
            await ctx.send(f"An unexpected error occurred during command execution: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Bloxlink(bot))