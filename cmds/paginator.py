import discord
from discord.ext import commands
import math

# Paginator built using https://www.youtube.com/watch?v=PRC4Ev5TJwc&t=1s
class PaginatorClass(commands.Cog):
    
    class Paginator(discord.ui.View):
    
        def __init__(self, items, item_type):
            super().__init__()
            self.items = items
            self.page = 1
            self.max_elems = 5
            self.start = 0
            self.end = 0
            self.item_type = item_type
    
        async def send(self, ctx):
            self.next_button.disabled = (len(self.items) < self.max_elems)
            self.message = await ctx.send(embed=self.create_embed(
                self.get_current_page_data()),
                                          view=self)
    
        def create_embed(self, items):
            embed = discord.Embed(
                title=
                f"{int(len(self.items))} {self.item_type}{'s' if int(len(self.items)) != 1 else ''} found",
                color=0x971B2F)
            for item in items:
                embed.add_field(name=item['item'],
                                value=item['details'],
                                inline=False)
            embed.set_footer(
                text=
                f"Showing results {int(self.start + 1)}-{int(self.end)} of {int(len(self.items))}. P{int(self.page)}/{int(math.ceil(len(self.items) / self.max_elems))}. Results provided by UMass Amherst Campus Pulse."
            )
            embed.set_thumbnail(
                url=
                "https://www.umass.edu/gss/sites/default/files/images/header/download.png"
            )
            return embed
    
        async def update_message(self, items):
            self.update_buttons()
            await self.message.edit(embed=self.create_embed(items), view=self)
    
        def update_buttons(self):
            if self.page == 1:
                self.first_page_button.disabled = True
                self.prev_button.disabled = True
            else:
                self.first_page_button.disabled = False
                self.prev_button.disabled = False
            if self.page == math.ceil(len(self.items) / self.max_elems):
                self.next_button.disabled = True
            else:
                self.next_button.disabled = False
    
        def get_current_page_data(self):
            self.start = (self.page - 1) * self.max_elems
            self.end = self.page * self.max_elems
            if self.page == math.ceil(len(self.items) / self.max_elems):
                self.end = len(self.items)
            return self.items[self.start:self.end]
    
        @discord.ui.button(label="1️⃣",
                           style=discord.ButtonStyle.green,
                           disabled=True)
        async def first_page_button(self, interaction, button):
            self.page = 1
            await self.update_message(self.get_current_page_data())
            await interaction.response.defer()
    
        @discord.ui.button(label="⬅️",
                           style=discord.ButtonStyle.grey,
                           disabled=True)
        async def prev_button(self, interaction, button):
            self.page -= 1
            await self.update_message(self.get_current_page_data())
            await interaction.response.defer()
    
        @discord.ui.button(label="➡️", style=discord.ButtonStyle.grey)
        async def next_button(self, interaction, button):
            self.page += 1
            await self.update_message(self.get_current_page_data())
            await interaction.response.defer()

async def setup(bot):
    await bot.add_cog(PaginatorClass(bot))
