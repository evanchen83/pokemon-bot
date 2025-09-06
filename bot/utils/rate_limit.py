import time
import functools
import os
from typing import Callable

from discord import Interaction
from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry


_redis = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
    retry=Retry(ExponentialBackoff(), retries=3),
)


def rate_limit(key_func: Callable[[Interaction], str], limit: int, period: int):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            interaction = next((arg for arg in args if isinstance(arg, Interaction)), kwargs.get("interaction"))
            if not interaction:
                raise ValueError("Missing Interaction argument for rate limiting")

            key = key_func(interaction)
            current = await _redis.incr(key)
            if current == 1:
                await _redis.expire(key, period)

            if current > limit:
                reset_time = int(time.time() + await _redis.ttl(key))
                await interaction.response.send_message(
                    f"⏳ Rate limited. Try again <t:{reset_time}:R>.",
                    ephemeral=True,
                )
                return

            return await func(*args, **kwargs)

        return wrapper
    return decorator
