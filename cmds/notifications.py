import discord
from discord.ext import commands
import requests
from datetime import datetime, timezone
import discord.ui
import sqlite3
import re
from table2ascii import table2ascii, PresetStyle


class NotificationsCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def is_valid_host_key(self, host_key_input: str,
                          clubs_data: dict) -> (bool, str):
        for club in clubs_data:
            if str(club['WebsiteKey']) == host_key_input:
                club_name = club['Name']
                return True, club_name
        return False, ""

    def is_valid_lead_time(self, lead_time: str) -> (bool, int):
        pattern = re.compile(r"(\d+h)?(\d+m)?$", re.IGNORECASE)
        match = pattern.match(lead_time)
        if match is None:
            return False, 0
        hours = match.group(1)
        minutes = match.group(2)

        if minutes:
            minutes = int(minutes[:-1])
            if minutes % 5 != 0 or minutes >= 60 or minutes <= 0:
                return False, 0
        else:
            minutes = 0

        if hours:
            hours = int(hours[:-1])
        else:
            hours = 0

        total = hours * 60 + minutes
        if total > 168 * 60:
            return False, 0
        return True, total

    @commands.command()
    async def notify(self, ctx):
        if ctx.guild == None:
            await ctx.send("You cannot send notifications to your DMs.")
            return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "You must have administrator permissions to create event notifications."
            )
            return
        # Establish connection to clubs page
        clubs_url = "https://umassamherst.campuslabs.com/engage/api/discovery/search/organizations?orderBy%5B0%5D=UpperName%20asc&top=99999&filter=&query="
        clubs_response = requests.get(clubs_url)
        clubs_data = clubs_response.json()
        clubs_data = clubs_data['value']

        # Used to wait for response from same user in same channel
        def check(message):
            return message.author.id == ctx.author.id and message.channel.id == ctx.channel.id

        # Enter host ID
        host_key_instructions = "Please enter a host identifier. This is the string that can be found in the host identifier field of !events, club identifier field of !clubs, or the last part of a club's URL on Campus Pulse (i.e. the `umoc` in `https://umassamherst.campuslabs.com/engage/organization/umoc`). Or, type `exit` to exit."
        await ctx.send(host_key_instructions)
        club_name = ""
        host_id = None
        while True:
            host_key_input = await self.bot.wait_for('message',
                                                     check=check,
                                                     timeout=120.0)
            is_valid, club_name = self.is_valid_host_key(
                host_key_input.content, clubs_data)
            if is_valid:
                for club in clubs_data:
                    if str(club['WebsiteKey']) == host_key_input.content:
                        host_id = str(club['Id'])
                break
            elif host_key_input.content.lower() == "exit":
                await ctx.send("Exited !notify.")
                return
            else:
                await ctx.send("Invalid entry. " + host_key_instructions)

        # Enter lead time
        lead_time_instructions = """Please enter your notification lead time(s). This is the amount of time before the organization's events when a notification will be sent to this channel. Minutes should be multiples of 5 (5, 10, 15...) and the total time should not exceed a week (168 hours). Or, type `exit` to exit. Syntax:
        `24h` - notifications for events will be sent 24 hours in advance.
        `2h30m` - notifications for events will be sent an two hours and 30 minutes in advance.
        `3h, 1h30m, 30m, 15m` - separate values with commas and spaces for 2+ multiple notifications. (If you want different messages for each, then create a unique notification for each lead time.)"""

        await ctx.send(lead_time_instructions)
        while True:
            lead_time_input = await self.bot.wait_for('message',
                                                      check=check,
                                                      timeout=120.0)
            if lead_time_input.content.lower() == "exit":
                await ctx.send("Exited !notify.")
                return

            # Turn commas into list partitions
            lead_time_list = [
                t.strip() for t in lead_time_input.content.split(',')
            ]

            minutes_list = []
            break_out = False

            # Check valid entry for each time entered
            for lead_time in lead_time_list:
                is_valid, minutes = self.is_valid_lead_time(lead_time)

                # If valid entry then convert to minutes and store in list, else throw error
                if is_valid:
                    minutes_list.append(minutes)
                    # If it is the last time in this loop, then all entries were valid, therefore break while loop
                    break_out = True
                else:
                    await ctx.send(f"Invalid entry `{lead_time}`. " +
                                   lead_time_instructions)
                    break

            if break_out:
                break

        # Enter roles
        roles_instructions = "Lastly, select the roles that you would like to be notified. Or, select `exit` to exit."

        view = discord.ui.View()
        view.add_item(
            self.RoleSelect(
                ctx, check, {
                    'club_name': club_name,
                    'host_key': host_key_input.content,
                    'host_id': host_id,
                    'lead_time': lead_time_input.content,
                    'minutes_list': minutes_list,
                    'channel_id': str(ctx.channel.id)
                }))

        await ctx.send(roles_instructions, view=view)

    class RoleSelect(discord.ui.Select):

        def __init__(self, ctx, check, data):
            options = []
            self.ctx = ctx
            self.check = check
            self.data = data
            for role in self.ctx.guild.roles:
                options.append(
                    discord.SelectOption(label=role.name, value=str(role.id)))

            options.append(
                discord.SelectOption(label="No roles", value="No roles"))
            options.append(discord.SelectOption(label="Exit", value="exit"))

            super().__init__(placeholder="Select the role(s) to mention:",
                             options=options,
                             max_values=len(options))

        async def callback(self, interaction: discord.Interaction):
            selected_options = self.values

            if "exit" in selected_options:
                await self.ctx.send("Exited !notify.")
                await interaction.response.defer()
                return

            if "No roles" in selected_options:
                selected_options = ["0"]
                roles_str = "No roles"
            else:
                roles_list = [
                    self.ctx.guild.get_role(int(role)).name
                    for role in selected_options
                ]
                roles_list = [
                    role[1:] if role == "@everyone" else role
                    for role in roles_list
                ]
                roles_str = ", ".join(roles_list)

            self.data.update({'roles': ",".join(selected_options)})

            self.disabled = True
            view = discord.ui.View()
            view.add_item(self)
            await interaction.response.edit_message(view=view)

            await self.ctx.bot.get_cog(
                'NotificationsCommands').handle_confirmation(
                    self.ctx, self.check, roles_str, **self.data)

    async def handle_confirmation(self, ctx, check, roles_str, **data):
        await ctx.send(f"""Confirm the following (type `yes`/`no`):
            Club/organization: {data['club_name']} (`{data['host_key']}`)
            When to send out notifications?: {data['lead_time']} before an event
            Who to notify?: {roles_str}
            """)

        confirm = await self.bot.wait_for('message',
                                          check=check,
                                          timeout=120.0)
        if confirm.content.lower() == "yes":
            await self.add_notification(ctx, data)
        else:
            await ctx.send("Please start again to continue.")

    async def add_notification(self, ctx, data):
        # Create the database and connection
        connection = sqlite3.connect("notifications_db.db")

        # Create a table for storing data
        connection.execute(
            "CREATE TABLE IF NOT EXISTS Event_notifications (notification_id INTEGER PRIMARY KEY, host_id TEXT, lead_time INTEGER, channel_id TEXT, roles TEXT);"
        )

        notifications_id_list = []
        for minutes in data['minutes_list']:
            # Retrieve the current maximum ID from the table
            cursor = connection.execute(
                "SELECT MAX(notification_id) FROM Event_notifications")
            notifications_max_id = cursor.fetchone()[0]
            notifications_next_id = notifications_max_id + 1 if notifications_max_id is not None else 1
            notifications_id_list.append(notifications_next_id)

            # Insert the new record with the generated ID
            connection.execute(
                "INSERT INTO Event_notifications (notification_id, host_id, lead_time, channel_id, roles) VALUES (?, ?, ?, ?, ?)",
                (notifications_next_id, str(data['host_id']), minutes,
                 data['channel_id'], data['roles']))

        connection.commit()

        # NOW CHECK IF THERE ARE ANY EVENTS IN WHICH THE NEW NOTIFICATION(S)' LEAD TIME HAS ALREADY EXPIRED

        current_date = datetime.now()
        current_date = datetime.strftime(current_date, '%Y-%m-%d')

        events_url = f"https://umassamherst.campuslabs.com/engage/api/discovery/event/search?endsAfter={current_date}T14%3A22%3A15-04%3A00&orderByField=endsOn&orderByDirection=ascending&status=Approved&take=99999&query="
        events_response = requests.get(events_url)
        events_data = events_response.json()
        events_data = events_data['value']

        for event in events_data:
            if str(event['organizationId']) == str(data['host_id']):
                for i, lead_time in enumerate(data['minutes_list']):
                    # Determine which events should not produce notifications
                    target_time = datetime.fromisoformat(
                        event['startsOn']).astimezone(timezone.utc)
                    current_time = datetime.now(timezone.utc)
                    datetime_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    time_difference = target_time - current_time
                    minutes_difference = int(time_difference.total_seconds() /
                                             60)

                    if minutes_difference < lead_time:
                        connection.execute(
                            "CREATE TABLE IF NOT EXISTS Notifications_log (log_id INTEGER PRIMARY KEY, event_id TEXT, notification_id INTEGER, time_sent DATETIME);"
                        )

                        cursor = connection.execute(
                            "SELECT MAX(log_id) FROM Notifications_log")
                        log_max_id = cursor.fetchone()[0]
                        log_next_id = log_max_id + 1 if log_max_id is not None else 1

                        connection.execute(
                            "INSERT INTO Notifications_log (log_id, event_id, notification_id, time_sent) VALUES (?, ?, ?, ?)",
                            (log_next_id, str(event['id']),
                             notifications_id_list[i], datetime_str))

                        # Commit changes
                        connection.commit()

        connection.close()

        await ctx.send("Your notifications have been confirmed.")

    @commands.group(invoke_without_command=True)
    async def notifications(self, ctx):
        try:
            channels = ctx.message.guild.text_channels
        except:
            await ctx.send("You cannot use !notifications in DMs.")
            return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "You must have administrator permissions to view event notifications."
            )
            return
        channel_ids = []
        for channel in channels:
            channel_ids.append(channel.id)

        connection = sqlite3.connect("notifications_db.db")
        cursor = connection.execute(
            f"SELECT * FROM Event_notifications WHERE channel_id IN ({', '.join('?' for channel_id in channel_ids)})",
            channel_ids)
        results = cursor.fetchall()

        connection.close()

        formatted_results = []

        clubs_url = "https://umassamherst.campuslabs.com/engage/api/discovery/search/organizations?orderBy%5B0%5D=UpperName%20asc&top=99999&filter=&query="
        clubs_response = requests.get(clubs_url)
        clubs_data = clubs_response.json()
        clubs_data = clubs_data['value']

        number = 1
        for result in results:
            club_name = ""
            for club in clubs_data:
                if str(club['Id']) == result[1]:
                    club_name = club['Name']
                    words = club_name.split()
                    club_name = '\n'.join([
                        ' '.join(words[i:i + 3])
                        for i in range(0, len(words), 3)
                    ])
                    break

            hours = result[2] // 60
            remaining_minutes = result[2] % 60

            time_str = ""

            if hours > 0 and remaining_minutes > 0:
                time_str = f"{hours} hours and {remaining_minutes} minutes"
            elif hours > 0:
                time_str = f"{hours} hours"
            elif remaining_minutes > 0:
                time_str = f"{remaining_minutes} minutes"
            else:
                time_str = ""

            channel = self.bot.get_channel(int(result[3]))

            roles = result[4].split(",")
            for i, role in enumerate(roles):
                if str(role) == "0":
                    roles = None
                else:
                    roles[i] = ctx.guild.get_role(int(role)).name
            if roles:
                roles = ",\n".join(roles)

            formatted_results.append(
                [number, club_name, time_str, channel.name, roles])
            number += 1

        output = table2ascii(
            header=[
                "Notification #", "Organization/club", "Lead time", "Channel",
                "Roles"
            ],
            body=formatted_results,
            # column_widths=[9, 39, 24, 20, 39],
            style=PresetStyle.ascii_box)

        await ctx.send(f"```{output}```")

    @notifications.command(aliases=['delete'])
    async def remove(self, ctx, args: str = None):
        try:
            channels = ctx.message.guild.text_channels
        except:
            await ctx.send("You cannot use `!notifications remove` in DMs.")
            return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "You must have administrator permissions to remove event notifications."
            )
            return

        channel_ids = []
        for channel in channels:
            channel_ids.append(channel.id)

        if args == "all":
            connection = sqlite3.connect("notifications_db.db")
            connection.execute(
                f"DELETE FROM Event_notifications WHERE channel_id IN ({', '.join('?' for channel_id in channel_ids)})",
                channel_ids)
            await ctx.send("Notifications successfully removed.")

        elif str(args).isdigit():
            connection = sqlite3.connect("notifications_db.db")
            cursor = connection.execute(
                f"SELECT * FROM Event_notifications WHERE channel_id IN ({', '.join('?' for channel_id in channel_ids)})",
                channel_ids)
            results_length = len(cursor.fetchall())
            if int(args) == 0 or int(args) > results_length:
                await ctx.send(f"Invalid notification #{args}.")
                return
            query_args = channel_ids + [int(args) - 1]
            connection.execute(
                f"""
            DELETE FROM Event_notifications
            WHERE notification_id IN (
                SELECT notification_id
                FROM Event_notifications
                WHERE channel_id IN ({', '.join('?' for channel_id in channel_ids)})
                LIMIT 1 OFFSET (?)
                );
            """, query_args)
            await ctx.send("Notification successfully removed.")

        else:
            await ctx.send(
                "You must enter a valid notification number or `all` to remove all notifications from this server. You can find a notification number to remove by running !notifications."
            )
            return

        connection.commit()
        connection.close()


async def setup(bot):
    await bot.add_cog(NotificationsCommands(bot))
