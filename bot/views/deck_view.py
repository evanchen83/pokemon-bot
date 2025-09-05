import discord
from discord.ui import View, button

MAX_CHARS_PER_PAGE = 1000 


class DeckView(View):
    def __init__(self, full_text: str):
        super().__init__(timeout=60)
        self.chunks = self._paginate_text(full_text)
        self.index = 0

    def _paginate_text(self, text: str) -> list[str]:
        """
        Splits the full deck text into pages, keeping set headers and adding "(continued...)" if needed.
        Adds space between sets for readability.
        """
        paragraphs = text.splitlines()
        chunks = []
        buffer = ""
        current_header = ""

        for line in paragraphs:
            if not line.strip():
                continue

            is_header = not line.startswith("•")
            if is_header:
                line = "\n" + line
                current_header = line.strip()

            preview = buffer + ("\n" if buffer else "") + line
            if len(preview) > MAX_CHARS_PER_PAGE:
                if buffer:
                    chunks.append(buffer.strip())
                if is_header:
                    buffer = line
                else:
                    buffer = f"{current_header} (continued...)\n{line}"
            else:
                buffer = preview

        if buffer:
            chunks.append(buffer.strip())

        return chunks

    @property
    def current_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📖 Your Pokémon Cards (Page {self.index + 1}/{len(self.chunks)})",
            description=self.chunks[self.index],
            color=discord.Color.blue()
        )
        return embed

    @button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await interaction.response.edit_message(embed=self.current_embed, view=self)
        else:
            await interaction.response.defer()

    @button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.chunks) - 1:
            self.index += 1
            await interaction.response.edit_message(embed=self.current_embed, view=self)
        else:
            await interaction.response.defer()
