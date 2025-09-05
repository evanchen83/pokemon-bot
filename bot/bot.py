import os
import json
import logging
import discord
from discord.ext import commands
from discord import app_commands

from bot.utils.logging_utils import (
    setup_logging,
    inject_log_context,
    log_time
)

setup_logging()
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="ping", description="Check if the bot is responsive and has access to sets.json.")
@inject_log_context
@log_time(logger.info)
async def ping(interaction: discord.Interaction):
    with open("data/sets.json", "r", encoding="utf-8") as f:
        sets_data = json.load(f)

    logger.info("Ping command executed")
    await interaction.response.send_message(sets_data[0])

@bot.event
async def setup_hook():
    await bot.load_extension("bot.commands.open_pack")
    await bot.load_extension("bot.commands.agent")
    await bot.load_extension("bot.commands.show_cards")


bot.run(os.getenv("DISCORD_BOT_TOKEN"))
