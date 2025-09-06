from pydantic_settings import BaseSettings  # ✅
from pydantic import Field

class BotSettings(BaseSettings):
    discord_bot_token: str = Field(..., alias="DISCORD_BOT_TOKEN")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    redis_host: str = Field(..., alias="REDIS_HOST")
    redis_port: int = Field(..., alias="REDIS_PORT")

    db_host: str = Field(..., alias="DB_HOST")
    db_port: int = Field(..., alias="DB_PORT")
    db_name: str = Field(..., alias="DB_NAME")
    db_user: str = Field(..., alias="DB_USER")
    db_password: str = Field(..., alias="DB_PASSWORD")

    class Config:
        secrets_dir = "/etc/secrets"

config = BotSettings()