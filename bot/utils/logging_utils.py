from functools import wraps
import logging
import contextvars
import discord
import json
import time
from typing import Callable
import asyncio
import uuid 
from discord.ext import commands

current_user_id = contextvars.ContextVar("current_user_id", default=None)
current_guild_id = contextvars.ContextVar("current_guild_id", default=None)
current_correlation_id = contextvars.ContextVar("correlation_id", default=None)


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()

    formatter = ContextInjectingFormatter("%(message)s")
    handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(handler)


class ContextInjectingFormatter(logging.Formatter):
    def format(self, record):
        user_id = current_user_id.get()
        guild_id = current_guild_id.get()
        correlation_id = current_correlation_id.get()
        message = super().format(record)

        log_output = {"user_id": user_id, "guild_id": guild_id, "correlation_id": correlation_id, "message": message}
        return json.dumps(log_output)

def inject_log_context(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if isinstance(args[0], commands.Cog):
            interaction = args[1] 
        else:
            interaction = args[0]  

        current_user_id.set(interaction.user.name)
        current_guild_id.set(interaction.guild.name if interaction.guild else None)
        current_correlation_id.set(uuid.uuid4().hex[:8]) 

        return await func(*args, **kwargs)
    return wrapper


def log_time(log_func: Callable, label: str | None = None):
    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = label or func.__name__
            log_func(f"[START] {name}")
            start = time.perf_counter()

            result = func(*args, **kwargs)

            duration_sec = round(time.perf_counter() - start, 2)
            log_func(f"[END] {name} - {duration_sec} sec")
            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = label or func.__name__
            log_func(f"[START] {name}")
            start = time.perf_counter()

            result = await func(*args, **kwargs)

            duration_sec = round(time.perf_counter() - start, 2)
            log_func(f"[END] {name} - {duration_sec} sec")
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
