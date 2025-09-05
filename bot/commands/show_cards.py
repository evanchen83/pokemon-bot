import json
import logging
from collections import defaultdict
from pathlib import Path

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from bot import db
from bot.utils.logging_utils import inject_log_context, log_time
from bot.views.deck_view import DeckView

logger = logging.getLogger(__name__)
DATA_DIR = Path("/app/data")


class ShowCardsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        with open(DATA_DIR / "cards.json", "r", encoding="utf-8") as f:
            self.cards_data = json.load(f)
        self.card_lookup = {card["id"]: card for card in self.cards_data}

    async def autocomplete_set_name(
        self,
        interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete handler: shows only sets the player owns cards from."""
        discord_id = str(interaction.user.id)
        player_cards = db.get_cards(discord_id)
        owned_sets = set()

        for card_id in player_cards:
            card = self.card_lookup.get(card_id)
            if card and "set" in card:
                set_name = card["set"].get("name")
                if set_name and current.lower() in set_name.lower():
                    owned_sets.add(set_name)

        return [
            app_commands.Choice(name=name, value=name)
            for name in sorted(owned_sets)[:25]
        ]

    @app_commands.command(name="show_cards", description="Show your collected Pokémon cards.")
    @app_commands.describe(set_name="Filter to a specific set")
    @app_commands.autocomplete(set_name=autocomplete_set_name)
    @inject_log_context
    @log_time(logger.info)
    async def show_cards(
        self,
        interaction: Interaction,
        set_name: str | None = None
    ):
        discord_id = str(interaction.user.id)
        player_cards = db.get_cards(discord_id)

        if not player_cards:
            await interaction.response.send_message("📭 You don't have any cards yet!")
            return

        grouped = defaultdict(list)
        for card_id, qty in player_cards.items():
            card = self.card_lookup.get(card_id)
            if not card:
                continue

            name = card.get("name", "Unknown")
            rarity = card.get("rarity", "Unknown")
            current_set = card.get("set", {}).get("name", "Unknown Set")

            if set_name and current_set != set_name:
                continue

            grouped[current_set].append(f"• {name} — {rarity} — x{qty}")

        if not grouped:
            await interaction.response.send_message(f"📭 You don't have any cards from the set **{set_name}**.")
            return

        parts = []
        for current_set, entries in grouped.items():
            parts.append(f"📦 **{current_set}**\n" + "\n".join(entries))
        full_text = "\n\n".join(parts)

        view = DeckView(full_text)
        await interaction.response.send_message(embed=view.current_embed, view=view)

        logger.info(f"{interaction.user} viewed their cards (set: {set_name or 'all'})")

async def setup(bot: commands.Bot):
    await bot.add_cog(ShowCardsCog(bot))