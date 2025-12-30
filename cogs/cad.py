import discord
from discord.ext import commands
import aiohttp
import asyncio

# ============================================================
# ⚙️ CAD CONFIGURATION
# ============================================================
SONORAN_API_KEY = "2939baa-49e1-4912-b1"
SONORAN_COMM_ID = "lkvcwl"
CAD_VERIFIED_ROLE_ID = 1439048210801885265

EMBED_COLOR = discord.Color.from_str("#757575")
FOOTER_TEXT = "LKVC - Sonoran Management System"


class CadVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # 1 use every 30 seconds per user to prevent blacklisting
        self._cd = commands.CooldownMapping.from_cooldown(1.0, 30.0, commands.BucketType.user)

    @discord.ui.button(
        label="Verify Sonoran CAD",
        style=discord.ButtonStyle.success,
        custom_id="persistent_cad_verify_btn"
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Check Cooldown
        bucket = self._cd.get_bucket(interaction.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return await interaction.response.send_message(
                f"⚠️ Please wait {round(retry_after, 1)}s before trying again.",
                ephemeral=True
            )

        # 2. Defer Immediately
        await interaction.response.defer(ephemeral=True)

        # Everything must be converted to a string to avoid 400 errors
        payload = {
            "id": str(SONORAN_COMM_ID),
            "key": str(SONORAN_API_KEY),
            "type": "GET_ACCOUNT",
            "data": [
                {
                    "discord": str(interaction.user.id)  # MUST be a string
                }
            ]
        }

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post("https://api.sonorancad.com/general/get_account", json=payload) as resp:

                    if resp.status == 400:
                        return await interaction.followup.send(
                            "❌ API Error 400: Data format incorrect. Check your IDs.", ephemeral=True)

                    if resp.status != 200:
                        return await interaction.followup.send(f"❌ Sonoran API Error (Status: {resp.status})",
                                                               ephemeral=True)

                    data = await resp.json()

                    # Logic: Sonoran returns a list of matching accounts
                    if isinstance(data, list) and len(data) > 0:
                        # Success check
                        role = interaction.guild.get_role(CAD_VERIFIED_ROLE_ID)
                        if role:
                            await interaction.user.add_roles(role)
                            await interaction.followup.send("✅ **Success!** Your account is linked.", ephemeral=True)
                        else:
                            await interaction.followup.send("❌ Error: Verification role not found in server.",
                                                            ephemeral=True)
                    else:
                        await interaction.followup.send(
                            "❌ Account not found. Ensure your Discord is linked in CAD Settings!", ephemeral=True)

        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Request timed out. Sonoran is slow right now.", ephemeral=True)
        except Exception as e:
            print(f"CAD API Error: {e}")
            await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)


class Cad(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(CadVerifyView())

    @commands.command(name="postverify")
    @commands.has_permissions(administrator=True)
    async def post_verify_cmd(self, ctx):
        embed = discord.Embed(
            title="Sonoran CAD Account Verification",
            description="Click the button below to link your Discord and verify your account.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=FOOTER_TEXT)
        await ctx.send(embed=embed, view=CadVerifyView())


async def setup(bot):
    await bot.add_cog(Cad(bot))