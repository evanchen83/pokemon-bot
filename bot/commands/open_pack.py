import json
import logging
import random
from pathlib import Path
from typing import Dict, List

from discord import Interaction, app_commands
from discord.ext import commands

from bot.utils.logging_utils import inject_log_context, log_time
from bot.views.pack_view import PackView
from bot import db 

logger = logging.getLogger(__name__)

DATA_DIR = Path("/app/data")


class OpenPackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        with open(DATA_DIR / "sets.json", "r", encoding="utf-8") as f:
            self.sets_data = json.load(f)

        with open(DATA_DIR / "cards.json", "r", encoding="utf-8") as f:
            self.cards_data = json.load(f)

        self.set_to_cards: Dict[str, List[dict]] = {}

        for card in self.cards_data:
            set_info = card.get("set", {})
            set_name = set_info.get("name")
            if not set_name:
                continue
            self.set_to_cards.setdefault(set_name, []).append(card)

        # Filter out sets that aren't openable
        for set_name in list(self.set_to_cards.keys()):
            cards = self.set_to_cards[set_name]

            commons = [c for c in cards if c.get("rarity", "").lower() == "common"]
            uncommons = [c for c in cards if c.get("rarity", "").lower() == "uncommon"]
            rares_or_better = [
                c
                for c in cards
                if c.get("rarity")
                and c.get("rarity", "").lower() not in ("common", "uncommon")
            ]

            sample_pack = (
                random.sample(commons, min(4, len(commons))) +
                random.sample(uncommons, min(3, len(uncommons))) +
                random.sample(rares_or_better, min(2, len(rares_or_better)))
            )

            all_have_images = all(
                c.get("images", {}).get("large") or c.get("images", {}).get("small")
                for c in sample_pack
            )

            if not (commons and uncommons and rares_or_better and all_have_images):
                del self.set_to_cards[set_name]

        logger.info(
            f"Filtered down to {len(self.set_to_cards)} openable sets "
            f"(total {len(self.cards_data)} cards)"
        )

    async def set_autocomplete(
        self,
        interaction: Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete set names."""
        return [
            app_commands.Choice(name=set_name, value=set_name)
            for set_name in self.set_to_cards
            if current.lower() in set_name.lower()
        ][:25]

    @app_commands.command(name="open_pack", description="Open a Pokémon booster pack!")
    @app_commands.describe(set_name="Choose a set to open a pack from")
    @app_commands.autocomplete(set_name=set_autocomplete)
    @inject_log_context
    @log_time(logger.info)
    async def open_pack(self, interaction: Interaction, set_name: str):
        if set_name not in self.set_to_cards:
            await interaction.response.send_message(
                f"⚠️ Set **{set_name}** is not openable. Please choose another.",
                ephemeral=True,
            )
            return

        cards = self.set_to_cards[set_name]

        commons = [c for c in cards if c.get("rarity", "").lower() == "common"]
        uncommons = [c for c in cards if c.get("rarity", "").lower() == "uncommon"]
        rares_or_better = [
            c
            for c in cards
            if c.get("rarity")
            and c.get("rarity", "").lower() not in ("common", "uncommon")
        ]

        pack = (
            random.sample(commons, min(4, len(commons))) +
            random.sample(uncommons, min(3, len(uncommons))) +
            random.sample(rares_or_better, min(2, len(rares_or_better)))
        )

        discord_id = str(interaction.user.id)
        new_cards = {}

        for card in pack:
            card_id = card["id"]
            new_cards[card_id] = new_cards.get(card_id, 0) + 1

        db.add_cards(discord_id, new_cards)
        
        image_urls = []
        for card in pack:
            img = card.get("images", {}).get("large") or card.get("images", {}).get(
                "small"
            )
            if img:
                image_urls.append(img)

        view = PackView(image_urls, set_name=set_name)
        await interaction.response.send_message(
            content=f"🎉 {interaction.user.mention} opened a pack from **{set_name}**!",
            embed=view.format_embed(),
            view=view,
        )

        logger.info(f"{interaction.user} opened a pack from {set_name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(OpenPackCog(bot))
