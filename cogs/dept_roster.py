import discord
from discord.ext import commands
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone


class SheetTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sheet = None
        # --- CONFIGURATION ---
        self.target_guild_id = 1445181271344025693
        self.nickname_guild_id = 1328475009542258688
        self.ztp_role_id = 1445185080531357882
        self.sheet_name = "DPS | Department of Public Safety Roster"

        # --- RANK HIERARCHY ---
        self.RANK_ORDER = {
            "Commissioner": 1,
            "Department Chief": 2,
            "Assistant Chief": 3,
            "Captain": 4,
            "Lieutenant": 5,
            "Sergeant": 6,
            "Corporal": 7,
            "Sr. Officer": 8,
            "Officer": 9,
            "Cadet": 10
        }

        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        try:
            creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open(self.sheet_name)
            self.sheet = self.spreadsheet.sheet1
            print(f"✅ Roster System: Ranking Order Active")
        except Exception as e:
            print(f"❌ Connection Error: {e}")

    def sort_roster(self):
        """Sorts the data and overwrites only the necessary cells"""
        try:
            # 1. Fetch current sheet data
            all_values = self.sheet.get_all_values()
            if len(all_values) < 4: return

            # 2. Extract rows starting from B4 (Index 3)
            # We slice [1:7] to get only Columns B through G
            data_rows = []
            for row in all_values[3:]:
                if len(row) > 3 and row[2].strip():  # Ensure there is a Rank to sort by
                    data_rows.append(row[1:7])

            if not data_rows: return

            # 3. Sort by RANK_ORDER
            def get_rank_priority(row):
                rank_name = row[2] if len(row) > 2 else ""  # Rank is Col D (index 2 in slice)
                return self.RANK_ORDER.get(rank_name, 99)

            sorted_data = sorted(data_rows, key=get_rank_priority)

            # 4. Update the range B4:G with sorted data
            self.sheet.update(f"B4:G{3 + len(sorted_data)}", sorted_data, value_input_option='USER_ENTERED')
            print(f"⚖️ Roster: Sorted {len(sorted_data)} members.")
        except Exception as e:
            print(f"❌ Sorting Error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.sheet:
            return

        if message.guild and message.guild.id == self.target_guild_id:
            member = message.author

            # 1. Nickname Logic
            nick_guild = self.bot.get_guild(self.nickname_guild_id)
            display_name = member.display_name
            if nick_guild:
                target_member = nick_guild.get_member(member.id)
                if target_member and target_member.nick:
                    display_name = target_member.nick

            # 2. Rank Logic
            roles = [role.name for role in member.roles if role.name != "@everyone"]
            highest_rank = member.top_role.name if roles else "Cadet"

            # 3. ZTP Logic
            ztp_val = "FALSE"
            if member.get_role(self.ztp_role_id):
                if member.joined_at and (datetime.now(timezone.utc) - member.joined_at).days <= 14:
                    ztp_val = "TRUE"

            # Data for B:G
            row_data = [
                display_name,  # B
                str(member.id),  # C
                highest_rank,  # D
                member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "N/A",  # E
                ztp_val,  # F
                "None"  # G
            ]

            try:
                # 4. Check if user is already on the sheet (Column C for ID)
                try:
                    found_cell = self.sheet.find(str(member.id), in_column=3)
                    self.sheet.update(f"B{found_cell.row}:G{found_cell.row}", [row_data],
                                      value_input_option='USER_ENTERED')
                except:
                    # 5. Manual Append to first empty row in Column B
                    col_b = self.sheet.col_values(2)
                    next_row = 4
                    for i in range(3, len(col_b)):
                        if not col_b[i].strip():
                            next_row = i + 1
                            break
                    else:
                        next_row = len(col_b) + 1

                    if next_row < 4: next_row = 4
                    self.sheet.update(f"B{next_row}:G{next_row}", [row_data], value_input_option='USER_ENTERED')

                # 6. Sort
                self.sort_roster()

            except Exception as e:
                print(f"❌ Sheet Update Error: {e}")


async def setup(bot):
    await bot.add_cog(SheetTracker(bot))