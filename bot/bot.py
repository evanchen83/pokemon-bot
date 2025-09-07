import logging
import discord
from discord.ext import commands
from bot.settings import config

from bot.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def setup_hook():
    await bot.load_extension("bot.commands.open_pack")
    await bot.load_extension("bot.commands.agent")
    await bot.load_extension("bot.commands.show_cards")
    await bot.load_extension("bot.commands.trade_card")


bot.run(config.discord_bot_token)
