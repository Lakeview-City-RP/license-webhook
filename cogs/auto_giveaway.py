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

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.gray)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        # CONFIG
        self.channel_id = 1146448285922500608
        self.role_id = 1442922648332927098
        self.trigger_messages = 600
        self.max_giveaways = 10
        self.giveaway_duration = 3600  # 1 hour
        self.prize_amount = 1000

        # STATE
        self.message_count = 0
        self.giveaway_count = 0
        self.giveaways = {}

        self.load_data()
        bot.loop.create_task(self.restore_giveaways())

    # ---------------- SAVE / LOAD ----------------

    def save_data(self):
        data = {
            "giveaway_count": self.giveaway_count,
            "giveaways": self.giveaways
        }
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

    # ---------------- EVENT LISTENER ----------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.channel.id != self.channel_id:
            return

        # HARD STOP after 10 giveaways (persistent)
        if self.giveaway_count >= self.max_giveaways:
            return

        # give role during event
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

    # ---------------- CREATE GIVEAWAY ----------------

    async def create_giveaway(self, channel: discord.TextChannel):
        # HARD STOP after 10 (persistent)
        if self.giveaway_count >= self.max_giveaways:
            return

        self.giveaway_count += 1

        giveaway_id = str(int(datetime.utcnow().timestamp() * 1000))
        end_time = datetime.utcnow() + timedelta(seconds=self.giveaway_duration)
        end_ts = int(end_time.timestamp())

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

        msg = await channel.send(
            content=f"<@&{self.role_id}>",
            embed=embed,
            view=view
        )
        await msg.pin()

        self.giveaways[giveaway_id]["message_id"] = msg.id
        self.save_data()

        asyncio.create_task(self.run_giveaway_loop(giveaway_id))

    # ---------------- EMBED BUILDER ----------------

    def build_embed(self, end_ts, entry_count, giveaways_left, guild):
        embed = discord.Embed(
            title="1,000 Robux Giveaway Spawned",
            description=(
                "> We are giving away 20,000 Robux for hitting 20,000 members, "
                "join the giveaway by clicking join below! "
                "Spawn more giveaways by sending messages in this channel.\n\n"
                f"**Entries:** {entry_count} | **Ending:** <t:{end_ts}:R>\n"
                f"**Giveaways Left:** {giveaways_left}"
            ),
            colour=discord.Colour.gold()
        )

        embed.set_thumbnail(url=THUMBNAIL_URL)

        if guild and guild.icon:
            embed.set_footer(
                text="Special 20,000 Member Event!",
                icon_url=guild.icon.url
            )
        else:
            embed.set_footer(text="Special 20,000 Member Event!")

        return embed

    # ---------------- GIVEAWAY LOOP ----------------

    async def run_giveaway_loop(self, giveaway_id):
        data = self.giveaways[giveaway_id]

        channel = self.bot.get_channel(data["channel_id"])
        if not channel:
            return

        try:
            msg = await channel.fetch_message(data["message_id"])
        except:
            return

        view = GiveawayView(giveaway_id, self)

        while True:
            await asyncio.sleep(1)

            now = int(datetime.utcnow().timestamp())
            if now >= data["end_ts"]:
                break

            try:
                giveaways_left = self.max_giveaways - self.giveaway_count
                embed = self.build_embed(data["end_ts"], len(data["entries"]), giveaways_left, channel.guild)
                await msg.edit(embed=embed, view=view)
            except:
                pass

        # END GIVEAWAY
        if not data["entries"]:
            await channel.send("No one joined the giveaway.")
        else:
            user_id = random.choice(data["entries"])
            user = await self.bot.fetch_user(user_id)
            await msg.reply(
                f"{user.mention} You won the giveaway for 1,000 robux, create a Purchase <#1134437443152650260> ticket!",
                mention_author=False
            )

        # Unpin message
        try:
            await msg.unpin()
        except:
            pass

        del self.giveaways[giveaway_id]
        self.save_data()

    # ---------------- RESTORE GIVEAWAYS ----------------

    async def restore_giveaways(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)

        for giveaway_id in list(self.giveaways.keys()):
            asyncio.create_task(self.run_giveaway_loop(giveaway_id))


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRobuxGiveaway(bot))
