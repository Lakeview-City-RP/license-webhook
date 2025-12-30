import discord
from discord.ext import commands
import asyncio
import random
import json
import os
from datetime import datetime, timedelta

THUMBNAIL_URL = "https://media.discordapp.net/attachments/1401973319296876614/1442926530287243405/robux--v2.png?ex=6927358d&is=6925e40d&hm=6eaf261c0a96b6f98aea91a9e4e749a1c73e7955c05eef8e2ea956c8ee45c189&=&format=png&quality=lossless&width=1006&height=1006"
DATA_FILE = "auto_giveaways.json"


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id, parent):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.parent = parent

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.gray, custom_id="join_giveaway_btn")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.giveaway_id not in self.parent.giveaways:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        data = self.parent.giveaways[self.giveaway_id]
        if interaction.user.id in data["entries"]:
            await interaction.response.send_message("You already joined.", ephemeral=True)
            return

        data["entries"].append(interaction.user.id)
        self.parent.save_data()
        await interaction.response.send_message("You have joined!", ephemeral=True)


class AutoRobuxGiveaway(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # CONFIG UPDATED
        self.channel_id = 1146448285922500608
        self.role_id = 1453804012624412749
        self.trigger_messages = 2000
        self.max_giveaways = 30 # Increased by 10
        self.giveaway_duration = 7200 # 2 Hours
        self.prize_amount = 1000

        # STATE
        self.message_count = 0
        self.giveaway_count = 0
        self.giveaways = {}

        self.load_data()
        bot.loop.create_task(self.restore_giveaways())

    def save_data(self):
        data = {"giveaway_count": self.giveaway_count, "giveaways": self.giveaways}
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    self.giveaway_count = data.get("giveaway_count", 0)
                    self.giveaways = data.get("giveaways", {})
            except:
                self.giveaway_count = 0
                self.giveaways = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.channel.id != self.channel_id:
            return

        if self.giveaway_count >= self.max_giveaways:
            return

        # Auto-Role
        role = message.guild.get_role(self.role_id)
        if role and role not in message.author.roles:
            try:
                await message.author.add_roles(role)
            except:
                pass

        self.message_count += 1

        if self.message_count >= self.trigger_messages:
            self.message_count = 0
            await self.create_giveaway(message.channel)

    async def create_giveaway(self, channel: discord.TextChannel):
        if self.giveaway_count >= self.max_giveaways:
            return

        self.giveaway_count += 1
        giveaway_id = str(int(datetime.utcnow().timestamp() * 1000))
        end_ts = int((datetime.utcnow() + timedelta(seconds=self.giveaway_duration)).timestamp())

        self.giveaways[giveaway_id] = {
            "channel_id": channel.id,
            "message_id": None,
            "end_ts": end_ts,
            "entries": []
        }
        self.save_data()

        view = GiveawayView(giveaway_id, self)
        giveaways_left = self.max_giveaways - self.giveaway_count
        embed = self.build_embed(end_ts, 0, giveaways_left, channel.guild)

        msg = await channel.send(content=f"<@&{self.role_id}>", embed=embed, view=view)
        try:
            await msg.pin()
        except:
            pass

        self.giveaways[giveaway_id]["message_id"] = msg.id
        self.save_data()
        asyncio.create_task(self.run_giveaway_loop(giveaway_id))

    def build_embed(self, end_ts, entry_count, giveaways_left, guild):
        embed = discord.Embed(
            title=f"{self.prize_amount:,} Robux Christmas Giveaway!",
            description=(
                f"> **Entries:** {entry_count}\n"
                f"> **Ending:** <t:{end_ts}:R>\n"
                f"> **Giveaways Remaining:** {giveaways_left}"
            ),
            colour=discord.Colour.green()
        )
        embed.set_thumbnail(url=THUMBNAIL_URL)
        footer_icon = guild.icon.url if guild and guild.icon else None
        embed.set_footer(text="Christmas Robux Giveaway!", icon_url=footer_icon)
        return embed

    async def run_giveaway_loop(self, giveaway_id):
        while True:
            if giveaway_id not in self.giveaways:
                return

            data = self.giveaways[giveaway_id]
            now = int(datetime.utcnow().timestamp())

            if now >= data["end_ts"]:
                break

            try:
                channel = self.bot.get_channel(data["channel_id"])
                if channel:
                    msg = await channel.fetch_message(data["message_id"])
                    giveaways_left = self.max_giveaways - self.giveaway_count
                    embed = self.build_embed(data["end_ts"], len(data["entries"]), giveaways_left, channel.guild)
                    await msg.edit(embed=embed, view=GiveawayView(giveaway_id, self))
            except:
                pass

            await asyncio.sleep(2)

        # END GIVEAWAY
        try:
            channel = self.bot.get_channel(data["channel_id"])
            msg = await channel.fetch_message(data["message_id"])
            await msg.unpin()

            if not data["entries"]:
                await channel.send(f"The giveaway ended, but no one joined!")
            else:
                winner_id = random.choice(data["entries"])
                winner = await self.bot.fetch_user(winner_id)
                await msg.reply(
                    f"🎊 {winner.mention} **You won 1,000 Robux!** Create a ticket at <#1134437443152650260>.")
        except:
            pass

        if giveaway_id in self.giveaways:
            del self.giveaways[giveaway_id]
            self.save_data()

    async def restore_giveaways(self):
        await self.bot.wait_until_ready()
        for giveaway_id in list(self.giveaways.keys()):
            asyncio.create_task(self.run_giveaway_loop(giveaway_id))


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRobuxGiveaway(bot))