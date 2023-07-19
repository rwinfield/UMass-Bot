import discord
from discord.ext import commands, tasks
import os
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timezone
from keep_alive import keep_alive
import html2text
import discord.ui
import sqlite3

prefix = "!"

bot = commands.Bot(command_prefix=prefix, intents=discord.Intents().all())

bot.remove_command('help')


@bot.event
async def on_ready():
    print('Logged in as {0.user}'.format(bot))
    cog_files = [
        'cmds.notifications', 'cmds.events', 'cmds.paginator', 'cmds.clubs'
    ]
    for cog_file in cog_files:
        await bot.load_extension(cog_file)
        print(f"{cog_file} has loaded.")

    await bot.change_presence(activity=discord.Game(name="!help"))

    connection = sqlite3.connect("notifications_db.db")

    connection.execute(
        "CREATE TABLE IF NOT EXISTS Event_notifications (notification_id INTEGER PRIMARY KEY, host_id TEXT, lead_time INTEGER, channel_id TEXT, roles TEXT);"
    )

    connection.execute(
        "CREATE TABLE IF NOT EXISTS Notifications_log (log_id INTEGER PRIMARY KEY, event_id TEXT, notification_id INTEGER, time_sent DATETIME);"
    )

    connection.commit()

    connection.close()

    auto_notifications.start()


@tasks.loop(seconds=30)
async def auto_notifications():
    connection = sqlite3.connect("notifications_db.db")

    current_date = datetime.now()
    current_date = datetime.strftime(current_date, '%Y-%m-%d')

    events_url = f"https://umassamherst.campuslabs.com/engage/api/discovery/event/search?endsAfter={current_date}T14%3A22%3A15-04%3A00&orderByField=endsOn&orderByDirection=ascending&status=Approved&take=99999&query="
    events_response = requests.get(events_url)
    events_data = events_response.json()
    events_data = events_data['value']

    current_time = datetime.now(timezone.utc)
    datetime_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

    for event in events_data:
        target_time = datetime.fromisoformat(event['startsOn']).astimezone(
            timezone.utc)
        time_difference = target_time - current_time
        minutes_difference = int(time_difference.total_seconds() / 60)

        # Select the notifications from the notifications table where the host ID = the organization namme and the lead time is greater than or equal to the time until that event. Do not send notifications where the notification has already been sent (when the notification ID appears in both AND the event ID appears in that entry from the notification log).
        cursor = connection.execute(f"""
        SELECT *
        FROM Event_notifications
        WHERE host_id = '{event['organizationId']}' AND lead_time >= {minutes_difference}
        AND NOT EXISTS (
          SELECT 1
          FROM Notifications_log
          WHERE Notifications_log.notification_id = Event_notifications.notification_id
            AND Notifications_log.event_id = {event['id']}
        )
        """)

        results = cursor.fetchall()

        if results:
            for result in results:
                notification_id, host_id, lead_time, channel_id, roles = result
                await send_notification(event, result)

                # Log the notification
                cursor = connection.execute(
                    "SELECT MAX(log_id) FROM Notifications_log")
                log_max_id = cursor.fetchone()[0]
                log_next_id = log_max_id + 1 if log_max_id is not None else 1

                connection.execute(
                    "INSERT INTO Notifications_log (log_id, event_id, notification_id, time_sent) VALUES (?, ?, ?, ?)",
                    (log_next_id, str(
                        event['id']), notification_id, datetime_str))

                # Commit changes
                connection.commit()

    connection.close()


async def send_notification(event, result):
    notification_id, host_id, lead_time, channel_id, roles = result

    if len(event["categoryNames"]) == 0:
        event["categoryNames"] = ["Other"]

    if event["theme"] == "ThoughtfulLearning":
        event["theme"] = "Learning"

    if event["theme"] == "CommunityService":
        event["theme"] = "Community Service"

    description = "N/A"
    if event["description"] is not None:
        description = html2text.html2text(event["description"],
                                          bodywidth=float('inf'))
        description = description[:500] + ("...\n"
                                           if len(description) > 300 else "")

    details = f"Theme: {event['theme']}\n"
    details += f"Host: {event['organizationName']}\n"
    details += f"Categor{'y' if len(event['categoryNames']) == 1 else 'ies'}: {', '.join(event['categoryNames'])}\n"
    details += f"Perk{'s' if len(event['benefitNames']) != 1 else ''}: "
    details += f"{', '.join(event['benefitNames'])}" if len(
        event['benefitNames']) >= 1 else "none"
    details += f"\nLocation: {event['location']}\n"

    date_format = "%Y-%m-%dT%H:%M:%S%z"
    starts_on = datetime.strptime(event['startsOn'], date_format)
    starts_on = int(starts_on.timestamp())

    ends_on = datetime.strptime(event['endsOn'], date_format)
    ends_on = int(ends_on.timestamp())

    details += f"Time: <t:{starts_on}> - <t:{ends_on}>\n"
    details += f"Description: _{description}_"

    embed = discord.Embed(title=format_duration(lead_time), color=0x971B2F)
    embed.add_field(
        name=
        f"{event['name']}\nhttps://umassamherst.campuslabs.com/engage/event/{event['id']}",
        value=details)
    embed.set_thumbnail(
        url=
        f"https://se-images.campuslabs.com/clink/images/{event['imagePath']}?preset=med-sq"
    )

    roles = roles.split(",")
    for i, role in enumerate(roles):
        if str(role) == "0":
            roles = None
        else:
            roles[i] = f"<@&{role}>"
    if roles:
        roles = ", ".join(roles)

    channel = bot.get_channel(int(channel_id))
    await channel.send(roles if roles else "", embed=embed)


def format_duration(minutes):
    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours > 0 and remaining_minutes > 0:
        return f"UPCOMING EVENT IN {hours} HOURS AND {remaining_minutes} MINUTES"
    elif hours > 0:
        return f"UPCOMING EVENT IN {hours} HOURS"
    elif remaining_minutes > 0:
        return f"UPCOMING EVENT IN {remaining_minutes} MINUTES"
    else:
        return "UPCOMING EVENT"


@bot.command()
async def invite(ctx):
    await ctx.send(
        "Invite me to your server!\nhttps://discord.com/api/oauth2/authorize?client_id=1123433115495440415&permissions=8&scope=bot"
    )


@bot.command()
async def help(ctx, args: str = None):
    embed = discord.Embed(title="UMass Bot Help", color=0x971B2F)
    if args == None:
        embed.add_field(
            name=
            f"Bot prefix: `{prefix}`. Run `{prefix}help [command]` for more information on any command.",
            value="",
            inline=False)
        embed.add_field(
            name="events",
            value=
            f"Show all events happening on campus. Optional field: `{prefix}events [mm/dd/yyyy]` to show events happening on or after a particular date."
        )
        embed.add_field(
            name="clubs",
            value=
            f"Aliases: `club`, `rso`, `rsos`\nShow all registered student organizations on campus. Optional field: `{prefix}clubs [search query]` to search for events matching your criteria.\nOptional field: `{prefix}clubs more [club identifier]` to view more information about a club.",
            inline=False)
        embed.add_field(
            name="notify",
            value=
            "SERVER ADMIN ONLY: Set notifications for events hosted by particular clubs/RSOs.",
            inline=False)
        embed.add_field(
            name="notifications",
            value=
            f"SERVER ADMIN ONLY: View your notifications in your server. `{prefix}remove [notification #]` to remove a notifiation.",
            inline=False)
        embed.add_field(
            name="dining",
            value=
            "Alias: `menu`\nFind today's menus for breakfast, lunch, or dinner at all four dining halls across campus.",
            inline=False)
        embed.add_field(
            name="invite",
            value=
            "Generate an invite link so you can add me to another server!",
            inline=False)
        embed.set_footer(
            text="UMass Bot was built and developed by fiat_multipla.")
        await ctx.send(embed=embed)

    elif args.lower() == "events":
        embed.add_field(
            name="Showing help for `events`",
            value=
            f"Aliases: None\nOptional argument: `[mm/dd/yyyy formatted date]`\nThis command will help find events according to your likings. Through a series of dropdowns, you can select your preferences and search for events that fit those critera. Additionally, you may enter a date, i.e. `{prefix}events 7/19/2023`, to only select events on or after a given day."
        )
        await ctx.send(embed=embed)

    elif args.lower() in {
            "clubs", "club", "rso", "rsos", "notify", "notifications",
            "notifications delete", "notifications remove"
    }:
        embed.add_field(name="Showing help for all club/RSO related commands",
                        value="",
                        inline=False)
        embed.add_field(
            name="clubs",
            value=
            f"Aliases: `club`, `rso`, `rsos`\nOptional argument: `[search query]`\nFind clubs and RSOs at UMass. A series of dropdowns will help filter results to your criteria. Additionally, you may enter a serarch query, i.e. `{prefix}clubs environmental`, to show clubs maktching a keyword or phrase.",
            inline=False)
        embed.add_field(
            name="clubs more",
            value=
            f"Aliases: Any of the above + `more`\nArgument: `[club identifier]`\nUse this to find more information on a club or RSO. This will provide a longer description, information about meeting dates, and social media links. Provide a club identifier which can be found when running the default `{prefix}clubs` command. This is also the WebsiteKey used in the last part of a club's URL on Campus Pulse (i.e. the `umoc` in https://umassamherst.campuslabs.com/engage/organization/umoc).",
            inline=False)
        embed.add_field(
            name="notify",
            value=
            "Aliases: None\nONLY SERVER ADMINISTRATORS MAY RUN THIS COMMAND.\nUse to add notifications about upcoming events to your Discord server! Enter the identifier for the host/club/RSO, specify the lead time(s) (amount of time before each event when you would like notifications to be sent), and then select the role(s) (if any) that you would like to be notified. Usage is step-by-step and a syntax guide is provided for each step. Notifications will be sent to the channel in which the command is used in. Useful for any club's Discord server that wants to send out reminders about their events.",
            inline=False)
        embed.add_field(
            name="notifications",
            value=
            "Aliases: None\nONLY SERVER ADMINISTRATORS MAY RUN THIS COMMAND.\nView the notifications enabled in your server.",
            inline=False)
        embed.add_field(
            name="notifications remove",
            value=
            f"Aliases: `notifications delete`\nArgument: `[notification #]` or `all`\nONLY SERVER ADMINISTRATORS MAY RUN THIS COMMAND.\nDelete a notification from your server. Use `{prefix}notifications` to find the notification # to remove. Or, you may use `all` to remove all notifications from your server.",
            inline=False)
        await ctx.send(embed=embed)

    elif args.lower() == {"dining", "menu"}:
        embed.add_field(
            name="Showing help for `dining`",
            value=
            "Alias: `menu`\nUse to find today's dining hall menus for breakfast, lunch, and dinner where applicable. Select a dining hall and a meal from the dropdown to view the menu."
        )
        await ctx.send(embed=embed)

    elif args.lower() == "invite":
        embed.add_field(
            name="Showing help for `invite`",
            value=
            "Aliases: None\nGenerate an invite link so you can add me to another server!"
        )
        await ctx.send(embed=embed)


class DiningMenu(discord.ui.Select):

    def __init__(self):
        meals = [
            discord.SelectOption(label="Breakfast"),
            discord.SelectOption(label="Lunch"),
            discord.SelectOption(label="Dinner"),
            discord.SelectOption(label="Late Night")
        ]

        dining_halls = [
            discord.SelectOption(label="Berkshire"),
            discord.SelectOption(label="Franklin"),
            discord.SelectOption(label="Hampshire"),
            discord.SelectOption(label="Worcester")
        ]

        options = dining_halls + meals

        super().__init__(placeholder="Select meal and a dining hall.",
                         max_values=2,
                         min_values=2,
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        meals = ["Breakfast", "Lunch", "Dinner", "Late Night"]
        dining_halls = ["Berkshire", "Franklin", "Hampshire", "Worcester"]

        if self.values[0] in meals and self.values[1] in meals or self.values[
                0] in dining_halls and self.values[1] in dining_halls:
            await interaction.response.send_message(
                "You must select a meal and a dining hall.")
            return

        if self.values[0] in meals:
            meal = self.values[0]
            dining_hall = self.values[1]
        else:
            meal = self.values[1]
            dining_hall = self.values[0]

        if dining_hall in ["Franklin", "Hampshire"] and meal == "Late Night":
            await interaction.response.send_message(
                f"{dining_hall} does not serve late night.")
            return

        if dining_hall == "Berkshire" and meal == "Breakfast":
            await interaction.response.send_message(
                "Berkshire does not serve breakfast.")
            return

        url = f"https://umassdining.com/locations-menus/{dining_hall.lower()}/menu#{meal.lower()}_menu"
        response = requests.get(url)
        html_content = response.text

        soup = BeautifulSoup(html_content, "html.parser")

        div_element = soup.find("div", class_=f"{meal.lower()}_fp")
        try:
            blocks = div_element.find_all(
                class_=lambda c: c in
                ["menu_category_name", "lightbox-nutrition"])
        except:
            await interaction.response.send_message(
                f"{dining_hall} is not currently open for {meal.lower()}.")
            return
        embed = discord.Embed(title=f"Today's {meal.lower()} at {dining_hall}",
                              color=0x971B2F)
        menu = []
        station = []
        for block in blocks:
            if "menu_category_name" in block["class"]:
                menu.append(station)
                station = []
                station.append(block.text.upper())
            else:
                station.append(block.text)

        menu.append(station)

        menu.pop(0)

        def compile_menu(station):
            station.pop(0)
            return ("\n".join(station))

        for station in menu:
            if station[0].startswith("LATINO"):
                station[0] = "LATINO"
            embed.add_field(name=station[0], value=compile_menu(station))

        embed.url = url
        embed.set_thumbnail(
            url=
            "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRaB98-pY_fxWXtCaNTQiLkJrJBZdkcu1-zMQ&usqp=CAU"
        )
        await interaction.response.send_message(embed=embed)


@bot.command(
    aliases=['menu'],
    brief=
    "Shows today's menus at dining halls. Run `!dining` or `!menu` then select a dining hall and meal to view a menu."
)
async def dining(ctx):
    view = discord.ui.View()
    view.add_item(DiningMenu())
    await ctx.send("Browse today's menus at the dining halls.", view=view)


try:
    keep_alive()
    bot.run(os.environ['TOKEN'])
except:
    os.system('kill 1')
