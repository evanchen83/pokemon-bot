import discord
from discord.ui import View, button
from typing import List


class PackView(View):
    def __init__(self, image_urls: List[str], set_name: str):
        super().__init__(timeout=60)
        self.image_urls = image_urls
        self.set_name = set_name
        self.index = 0

    def format_embed(self) -> discord.Embed:
        """Return an embed showing the current card image."""
        url = self.image_urls[self.index]
        embed = discord.Embed(
            title=f"{self.set_name} – Card {self.index + 1}/{len(self.image_urls)}",
            color=discord.Color.blue(),
        )
        embed.set_image(url=url)
        return embed

    @button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await interaction.response.edit_message(
                embed=self.format_embed(), view=self
            )
        else:
            await interaction.response.defer()

    @button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.image_urls) - 1:
            self.index += 1
            await interaction.response.edit_message(
                embed=self.format_embed(), view=self
            )
        else:
            await interaction.response.defer()

    @button(label="Reveal All", style=discord.ButtonStyle.success)
    async def reveal_all(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Send all cards at once and disable buttons."""
        embeds: List[discord.Embed] = []
        for idx, url in enumerate(self.image_urls, start=1):
            embed = discord.Embed(
                title=f"{self.set_name} – Card {idx}/{len(self.image_urls)}",
                color=discord.Color.green(),
            )
            embed.set_image(url=url)
            embeds.append(embed)

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"📦 Full **{self.set_name}** pack revealed!",
            embeds=embeds[:10],  # Discord limit
            view=self,
        )
