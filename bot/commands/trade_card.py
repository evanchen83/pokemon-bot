import asyncio
import json
import logging
from pathlib import Path

import discord
from discord import Interaction, app_commands, Member
from discord.ext import commands

from bot import db
from bot.utils.logging_utils import inject_log_context, log_time

logger = logging.getLogger(__name__)
DATA_DIR = Path("/app/data")


class TradeCardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open(DATA_DIR / "cards.json", encoding="utf-8") as f:
            self.cards_data = json.load(f)
        self.card_lookup = {card["id"]: card for card in self.cards_data}

    def get_sets_for_user(self, discord_id: str) -> list[str]:
        player_cards = db.get_cards(discord_id)
        sets = set()
        for card_id in player_cards:
            card = self.card_lookup.get(card_id)
            if card:
                set_name = card.get("set", {}).get("name")
                if set_name:
                    sets.add(set_name)
        return sorted(sets)

    def get_cards_for_user_in_set(self, discord_id: str, set_name: str) -> list[str]:
        player_cards = db.get_cards(discord_id)
        cards = []
        for card_id in player_cards:
            card = self.card_lookup.get(card_id)
            if card and card.get("set", {}).get("name") == set_name:
                cards.append(card.get("name", "Unknown"))
        return sorted(set(cards))

    async def autocomplete_set(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        sets = self.get_sets_for_user(user_id)
        return [
            app_commands.Choice(name=s, value=s)
            for s in sets if current.lower() in s.lower()
        ][:25]

    async def autocomplete_card(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        options = {opt["name"]: opt["value"] for opt in interaction.data.get("options", [])}
        selected_set = options.get("my_set") or ""
        cards = self.get_cards_for_user_in_set(user_id, selected_set)
        return [
            app_commands.Choice(name=c, value=c)
            for c in cards if current.lower() in c.lower()
        ][:25]

    async def autocomplete_their_set(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        options = {opt["name"]: opt["value"] for opt in interaction.data.get("options", [])}
        target = options.get("target_user")

        if not target:
            return []

        sets = self.get_sets_for_user(str(target))
        return [
            app_commands.Choice(name=s, value=s)
            for s in sets if current.lower() in s.lower()
        ][:25]

    async def autocomplete_their_card(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        options = {opt["name"]: opt["value"] for opt in interaction.data.get("options", [])}
        target = options.get("target_user")
        set_name = options.get("their_set") or ""

        if not target:
            return []

        cards = self.get_cards_for_user_in_set(str(target), set_name)
        return [
            app_commands.Choice(name=c, value=c)
            for c in cards if current.lower() in c.lower()
        ][:25]

    @app_commands.command(name="trade_card", description="Trade a card with another user.")
    @app_commands.describe(
        my_set="Your card's set",
        my_card="Your card name",
        target_user="The user you want to trade with",
        their_set="Their card's set",
        their_card="Their card name",
    )
    @app_commands.autocomplete(
        my_set=autocomplete_set,
        my_card=autocomplete_card,
        their_set=autocomplete_their_set,
        their_card=autocomplete_their_card,
    )
    @inject_log_context
    @log_time(logger.info)
    async def trade_card(
        self,
        interaction: Interaction,
        my_set: str,
        my_card: str,
        target_user: Member,
        their_set: str,
        their_card: str,
    ):
        initiator_id = str(interaction.user.id)
        target_id = str(target_user.id)

        my_card_id = next(
            (c["id"] for c in self.cards_data if c["name"] == my_card and c["set"]["name"] == my_set),
            None,
        )
        their_card_id = next(
            (c["id"] for c in self.cards_data if c["name"] == their_card and c["set"]["name"] == their_set),
            None,
        )

        if not my_card_id or not their_card_id:
            await interaction.response.send_message("❌ Invalid card selection.", ephemeral=True)
            return

        initiator_cards = db.get_cards(initiator_id)
        target_cards = db.get_cards(target_id)
        
        if initiator_cards.get(my_card_id, 0) < 1:
            await interaction.response.send_message("❌ You don't have that card.", ephemeral=True)
            return
        if target_cards.get(their_card_id, 0) < 1:
            await interaction.response.send_message(f"❌ {target_user.display_name} doesn't have that card.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔁 Trade Request",
            description=(
                f"**{interaction.user.display_name}** wants to trade with **{target_user.display_name}**!\n\n"
                f"**You give:** {my_card} ({my_set})\n"
                f"**You get:** {their_card} ({their_set})\n\n"
                f"{target_user.mention}, react below to accept or reject."
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def check(reaction, user):
            return (
                user.id == target_user.id
                and str(reaction.emoji) in {"✅", "❌"}
                and reaction.message.id == message.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            if str(reaction.emoji) == "✅":
                db.remove_cards(initiator_id, {my_card_id: 1})
                db.add_cards(target_id, {my_card_id: 1})
                db.remove_cards(target_id, {their_card_id: 1})
                db.add_cards(initiator_id, {their_card_id: 1})
                await message.reply("✅ Trade completed!")
                logger.info(f"{interaction.user} traded {my_card} with {target_user} for {their_card}")
            else:
                await message.reply("❌ Trade declined.")
        except asyncio.TimeoutError:
            await message.reply("⏱️ Trade timed out.")

async def setup(bot: commands.Bot):
    await bot.add_cog(TradeCardCog(bot))
