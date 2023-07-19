import discord
from discord.ext import commands
import discord.ui
import requests
from urllib.parse import urlencode, quote
import html2text

class ClubsCommands(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
    
    class ClubMenu(discord.ui.Select):
    
        def __init__(self, ctx, args):
            self.ctx = ctx
            self.args = args
            options = [
                discord.SelectOption(label="ALL CATEGORIES"),
                discord.SelectOption(label="Academic Council", value=1232),
                discord.SelectOption(label="Advocacy Council", value=1237),
                discord.SelectOption(label="Arts & Media Council", value=1233),
                discord.SelectOption(label="Club Sport Council", value=1242),
                discord.SelectOption(label="Cultural Council", value=1234),
                discord.SelectOption(label="Graduate Student Organizations",
                                     value=6855),
                discord.SelectOption(label="Greek Life - Fraternity", value=8127),
                discord.SelectOption(label="Interfraternity Council", value=1235),
                discord.SelectOption(label="Multicultural Greek Council",
                                     value=6498),
                discord.SelectOption(label="National Pan-Hellenic Council",
                                     value=6964),
                discord.SelectOption(label="Other", value=8129),
                discord.SelectOption(label="Panhellenic Council", value=1241),
                discord.SelectOption(label="Recreation Council", value=2445),
                discord.SelectOption(label="Religious & Spiritual Council",
                                     value=1238),
                discord.SelectOption(label="Residential Life", value=1229),
                discord.SelectOption(label="Service & Engagement Council",
                                     value=1240),
                discord.SelectOption(label="Student Businesses", value=1243),
                discord.SelectOption(label="Student Government Organizations",
                                     value=1236)
            ]
    
            super().__init__(placeholder="Select one or more category/ies.",
                             min_values=1,
                             max_values=len(options),
                             options=options)
    
        async def callback(self, interaction: discord.Interaction):
            selected_values = self.values
            if "ALL CATEGORIES" in selected_values:
                selected_values = "ALL CATEGORIES"
    
            category_query = ""
    
            if selected_values != "ALL CATEGORIES":
                i = 0
                for category in selected_values:
                    if i != 0:
                        category_query += f"or(CategoryIds%2Fany(x%3A%20x%20eq%20%27{category}%27))"
                    else:
                        category_query += f"filter=(CategoryIds%2Fany(x%3A%20x%20eq%20%27{category}%27))"
                    i += 1
                category_query += "&"
    
            query_string = category_query
    
            if len(self.args) > 0:
                input_query = quote(self.args[0])
                query = {'query': input_query}
    
                query_string += urlencode(query)
    
            url = f"https://umassamherst.campuslabs.com/engage/api/discovery/search/organizations?orderBy%5B0%5D=UpperName%20asc&top=99999&{query_string}&skip=0"
    
            response = requests.get(url)
            data = response.json()
            clubs = data['value']
            clubs_list = []
    
            for club in clubs:
                clubs_list.append(self.ctx.bot.get_cog('ClubsCommands').club_extractor(club))
    
            paginator_view = self.ctx.bot.get_cog('PaginatorClass').Paginator(items=clubs_list, item_type="club")
            await paginator_view.send(self.ctx)
            await interaction.response.defer()
    
    
    def club_extractor(self, club):
        for key, value in club.items():
            if key == 'Name':
                name = value
            elif key == 'CategoryNames':
                category = "N/A"
                if len(value
                       ) == 1 and value[0] == "Graduate Student Organizations":
                    category = "Graduate Student Organizations"
                if len(value) > 1:
                    category = value[1]
            elif key == 'WebsiteKey':
                identifier = "N/A"
                if identifier is not None:
                    identifier = value
            elif key == 'Description':
                description = "N/A"
                if value is not None:
                    description = html2text.html2text(value,
                                                      bodywidth=float('inf'))
                    description = description[:300] + (
                        "...\n" if len(description) > 300 else "")
    
        return {
            "item":
            name,
            "details":
            f"Category: {category}\nClub Indentifier: `{identifier}`\nDescription: _{description}_"
        }
    
    
    def more_clubs(self, identifier):
        all_clubs_url = "https://umassamherst.campuslabs.com/engage/api/discovery/search/organizations?orderBy%5B0%5D=UpperName%20asc&top=99999&skip=0"
        response = requests.get(all_clubs_url)
        data = response.json()
        clubs = data['value']
    
        i = 0
        for club in clubs:
            if club["WebsiteKey"] == identifier:
                break
            i += 1
            if i == len(clubs):
                return discord.Embed(title="No events found with that identifier.",
                                     color=0x971B2F)
    
        category = "N/A"
        if len(
                club["CategoryNames"]
        ) == 1 and club["CategoryNames"][0] == "Graduate Student Organizations":
            category = "Graduate Student Organizations"
        if len(club["CategoryNames"]) > 1:
            category = club["CategoryNames"][1].strip()
    
        club_url = f"https://umassamherst.campuslabs.com/engage/api/discovery/organization/{club['Id']}/?"
        response = requests.get(club_url)
        data = response.json()
    
        addtl_info_url = f"https://umassamherst.campuslabs.com/engage/api/discovery/organization/{club['Id']}/additionalFields?"
        addtl_info_response = requests.get(addtl_info_url)
        addtl_info_data = addtl_info_response.json()
    
        try:
            meeting_info = addtl_info_data["items"][0]["freeText"]
        except:
            meeting_info = ""
    
        club_info = {
            "Name": data["name"],
            "Alias": data["shortName"],
            "Identifier": "`" + str(identifier) + "`",
            "Category": category,
            "Description": html2text.html2text(data["description"], bodywidth=float('inf'))[:1024]
            if data["description"] else "N/A",
            "Meeting Info": meeting_info,
            ":e_mail: Email": data["email"],
            ":camera: Instagram": data["socialMedia"]["InstagramUrl"],
            ":arrow_forward: YouTube": data["socialMedia"]["YoutubeUrl"],
            ":regional_indicator_f: Facebook": data["socialMedia"]["FacebookUrl"],
            ":dove: Twitter": data["socialMedia"]["TwitterUrl"]
        }
    
        embed = discord.Embed(title=f"{club_info['Name']}", color=0x971B2F)
        i = 0
        for key, value in club_info.items():
            if i > 0:
                if not (value == "" or value == None):
                    embed.add_field(name=key, value=value, inline=False)
            i += 1
    
        embed.url = f"https://umassamherst.campuslabs.com/engage/organization/{identifier}"
        image = club["ProfilePicture"]
        embed.set_thumbnail(
            url=
            f"https://se-images.campuslabs.com/clink/images/{image}?preset=med-sq")
        embed.set_footer(text="RSO information provided by UMass Campus Pulse.")
        return embed
    
    
    @commands.command(
        aliases=['club', 'rso', 'rsos'],
        case_insensitive=True,
        brief=
        "Find Registered Student Organizations (RSOs) at UMass! Run `!clubs` or `rsos` for more detail."
    )
    async def clubs(self, ctx, *args):
        view = discord.ui.View()
        if len(args) == 1 and args[0] == "more":
            await ctx.send(
                "To find more information on a club, run `!clubs more [identifier]`."
            )
            return
        if len(args) == 2 and args[0] == "more":
            await ctx.send(embed=self.more_clubs(args[1]))
            return
        view.add_item(self.ClubMenu(ctx=ctx, args=args))
        join = ' '.join(args) if args else '(none)'
        await ctx.send(
            f"Search query: `{join}`. Next, select the club categories (the top option will show all):",
            view=view)

async def setup(bot):
    await bot.add_cog(ClubsCommands(bot))