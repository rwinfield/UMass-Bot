import discord
from discord.ext import commands
import requests
from datetime import datetime
import html2text
import discord.ui


class EventsCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def host_id(self, id: int, clubs_data: dict) -> str:
        for club in clubs_data:
            if int(club['Id']) == id:
                return club['WebsiteKey']
        return "None"

    def is_date(self, date):
        date_format = "%m/%d/%Y"
        try:
            bool(datetime.strptime(str(date), date_format))
            return True
        except ValueError:
            return False

    class EventThemes(discord.ui.Select):

        def __init__(self, selected_options, ctx, date_arg):
            options = [
                discord.SelectOption(label="ALL THEMES", value="ALL"),
                discord.SelectOption(label="Arts & Music", value="Arts"),
                discord.SelectOption(label="Cultural", value="Cultural"),
                discord.SelectOption(label="Service",
                                     value="CommunityService"),
                discord.SelectOption(label="Social", value="Social"),
                discord.SelectOption(label="Learning",
                                     value="ThoughtfulLearning")
            ]
            super().__init__(placeholder="Select themes.",
                             options=options,
                             custom_id="EventThemes",
                             min_values=1,
                             max_values=len(options))
            self.selected_options = selected_options
            self.date_arg = date_arg
            self.ctx = ctx

        async def callback(self, interaction: discord.Interaction):
            selections = interaction.data['values']
            self.selected_options.update({"theme": selections})
            view = discord.ui.View()
            view.add_item(
                self.ctx.bot.get_cog('EventsCommands').EventCategories(
                    self.selected_options, self.ctx, self.date_arg))
            await interaction.response.edit_message(
                content='Please select your category/ies:', view=view)

    class EventCategories(discord.ui.Select):

        def __init__(self, selected_options, ctx, date_arg):
            options = [
                discord.SelectOption(label="ALL CATEGORIES", value="ALL"),
                discord.SelectOption(label="Awards", value="Awards"),
                discord.SelectOption(label="Community Service",
                                     value="Community Service"),
                discord.SelectOption(label="Cultural-based",
                                     value="Cultural-based"),
                discord.SelectOption(label="Music", value="Music"),
                discord.SelectOption(label="Other", value="Other"),
                discord.SelectOption(label="Performance", value="Performance"),
                discord.SelectOption(label="Rehearsal/Practice",
                                     value="Rehearsal/Practice"),
                discord.SelectOption(label="Training/Workshop",
                                     value="Training/workshop"),
            ]
            super().__init__(placeholder="Select categories.",
                             options=options,
                             custom_id="EventCategories",
                             min_values=1,
                             max_values=len(options))
            self.selected_options = selected_options
            self.date_arg = date_arg
            self.ctx = ctx

        async def callback(self, interaction: discord.Interaction):
            selections = interaction.data['values']
            self.selected_options.update({"categoryNames": selections})
            view = discord.ui.View()
            view.add_item(
                self.ctx.bot.get_cog('EventsCommands').EventPerks(
                    self.selected_options, self.ctx, self.date_arg))
            await interaction.response.edit_message(
                content='Please select your perk(s):', view=view)

    class EventPerks(discord.ui.Select):

        def __init__(self, selected_options, ctx, date_arg):
            options = [
                discord.SelectOption(label="DOES NOT MATTER", value="ALL"),
                discord.SelectOption(label="Free Food", value="Free Food"),
                discord.SelectOption(label="Free Stuff", value="Free Stuff")
            ]
            super().__init__(
                placeholder="Select any perks or choose 'DOES NOT MATTER'.",
                options=options,
                custom_id="EventPerks",
                min_values=1,
                max_values=len(options))
            self.selected_options = selected_options
            self.date_arg = date_arg
            self.ctx = ctx

        async def callback(self, interaction: discord.Interaction):
            selections = interaction.data['values']
            self.selected_options.update({"benefitNames": selections})

            event_matches = self.ctx.bot.get_cog(
                'EventsCommands').process_options(self.selected_options,
                                                  self.date_arg)
            paginator_view = self.ctx.bot.get_cog('PaginatorClass').Paginator(
                items=event_matches, item_type="event")
            await paginator_view.send(self.ctx)
            await interaction.response.defer()

    def process_options(self, selected_options, date_arg):
        #CHECK IF USER PASSED IN A DATE, AND IF NOT, DEFAULT TO BELOW
        if date_arg == "":
            date_arg = datetime.now()
        else:
            #parse date
            date_arg = datetime.strptime(date_arg, '%m/%d/%Y')
        date_arg = datetime.strftime(date_arg, '%Y-%m-%d')

        events_url = f"https://umassamherst.campuslabs.com/engage/api/discovery/event/search?endsAfter={date_arg}T14%3A22%3A15-04%3A00&orderByField=endsOn&orderByDirection=ascending&status=Approved&take=99999&query="
        events_response = requests.get(events_url)
        events_data = events_response.json()
        events_data = events_data['value']

        clubs_url = "https://umassamherst.campuslabs.com/engage/api/discovery/search/organizations?orderBy%5B0%5D=UpperName%20asc&top=99999&filter=&query="
        clubs_response = requests.get(clubs_url)
        clubs_data = clubs_response.json()
        clubs_data = clubs_data['value']

        # if a user selected ALL and other options, set to just ALL
        for key, value in selected_options.items():
            if "ALL" in value:
                selected_options[key][0] = "ALL"

        for key in selected_options:
            event_matches = []
            for value in selected_options[key]:
                for event in events_data:
                    if len(event["categoryNames"]) == 0:
                        event["categoryNames"] = ["Other"]
                    if value in event[key] or value == "ALL":
                        event_matches.append(event)
            events_data = event_matches

        ret_str = []
        i = 0
        for event in events_data:
            i += 1

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
                description = description[:300] + (
                    "...\n" if len(description) > 300 else "")

            details = f"Theme: {event['theme']}\n"
            details += f"Host: {event['organizationName']} (identifier: `{self.host_id(event['organizationId'], clubs_data)}`)\n"
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

            ret_str.append({
                "item":
                f"#{i}: {event['name']}\nhttps://umassamherst.campuslabs.com/engage/event/{event['id']}",
                "details": details
            })

        return ret_str

    @commands.command(
        brief=
        "Find events happening at UMass Amherst! !events or !events mm/dd/yyyy to view events on and after a particular date."
    )
    async def events(self, ctx, *args):
        selected_options = {}
        view = discord.ui.View()
        if args and not self.is_date(args[0]):
            await ctx.send(
                "Invalid date entered. Please enter in the format `mm/dd/yyyy` or simply run `!events` to view all events starting from today."
            )
            return
        date_arg = ""
        if args and self.is_date(args[0]):
            date_arg = args[0]
        view.add_item(
            self.EventThemes(selected_options=selected_options,
                             ctx=ctx,
                             date_arg=date_arg))
        await ctx.send(content='Please select your theme(s):', view=view)


async def setup(bot):
    await bot.add_cog(EventsCommands(bot))
