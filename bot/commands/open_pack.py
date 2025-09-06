import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from discord import Interaction, app_commands
from discord.ext import commands

from bot import db
from bot.utils.logging_utils import inject_log_context, log_time
from bot.utils.rate_limit import rate_limit
from bot.views.pack_view import PackView

logger = logging.getLogger(__name__)

DATA_DIR = Path("/app/data")

RARITY_TIERS = {
    "common": {
        "names": {"common"},
        "weight": 60,
    },
    "uncommon": {
        "names": {"uncommon"},
        "weight": 25,
    },
    "rare": {
        "names": {
            "rare",
            "rare holo",
            "rare ace",
            "rare break",
            "rare prism star",
            "rare shining",
            "rare shiny",
            "rare holo star",
            "trainer gallery rare holo",
            "black white rare",
            "legend",
            "rare prime",
            "illustration rare",
        },
        "weight": 10,
    },
    "ultra_rare": {
        "names": {
            "rare holo ex",
            "rare holo gx",
            "rare holo lv.x",
            "rare holo v",
            "rare holo vmax",
            "rare holo vstar",
            "ultra rare",
            "double rare",
            "rare ultra",
            "shiny rare",
            "amazing rare",
            "radiant rare",
            "classic collection",
            "ace spec rare",
            "promo",
        },
        "weight": 4,
    },
    "secret_rare": {
        "names": {
            "rare shiny gx",
            "rare rainbow",
            "rare secret",
            "shiny ultra rare",
            "special illustration rare",
            "hyper rare",
        },
        "weight": 1,
    },
}


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

        # Filter only sets with enough diversity to open packs
        for set_name in list(self.set_to_cards.keys()):
            categorized = self._categorize_cards(self.set_to_cards[set_name])
            if (
                len(categorized["common"]) >= 5
                and len(categorized["uncommon"]) >= 3
                and len(self.set_to_cards[set_name]) >= 9
            ):
                continue
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
        return [
            app_commands.Choice(name=set_name, value=set_name)
            for set_name in self.set_to_cards
            if current.lower() in set_name.lower()
        ][:25]

    def _categorize_cards(self, cards: List[dict]) -> Dict[str, List[dict]]:
        categorized = defaultdict(list)
        for card in cards:
            rarity = card.get("rarity", "").lower()
            for tier, data in RARITY_TIERS.items():
                if rarity in {r.lower() for r in data["names"]}:
                    categorized[tier].append(card)
                    break
        return categorized

    def _weighted_choice(self, rarity_pools: Dict[str, List[dict]]) -> dict | None:
        pool = []
        for tier in ("rare", "ultra_rare", "secret_rare"):
            cards = rarity_pools.get(tier, [])
            weight = RARITY_TIERS[tier]["weight"]
            pool.extend(cards * weight)
        return random.choice(pool) if pool else None

    @app_commands.command(name="open_pack", description="Open a Pokémon booster pack!")
    @app_commands.describe(set_name="Choose a set to open a pack from")
    @app_commands.autocomplete(set_name=set_autocomplete)
    @rate_limit(key_func=lambda i: f"open_pack_daily:{i.user.id}", limit=5, period=86400)
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
        rarity_pools = self._categorize_cards(cards)

        pack = []

        pack += random.sample(
            rarity_pools["common"],
            min(5, len(rarity_pools["common"]))
        )
        pack += random.sample(
            rarity_pools["uncommon"],
            min(3, len(rarity_pools["uncommon"]))
        )

        # Reverse holo - any card in the set
        reverse_holo = random.choice(cards)
        pack.append(reverse_holo)

        # Rare slot - weighted choice from rare and above
        rare_card = self._weighted_choice(rarity_pools)
        if rare_card:
            pack.append(rare_card)

        # Track new cards
        discord_id = str(interaction.user.id)
        new_cards = {}
        for card in pack:
            card_id = card["id"]
            new_cards[card_id] = new_cards.get(card_id, 0) + 1

        db.add_cards(discord_id, new_cards)

        image_urls = []
        for card in pack:
            img = card.get("images", {}).get("large") or card.get("images", {}).get("small")
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