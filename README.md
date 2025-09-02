## Setup Instructions

To configure the bot, set the following environment variables in your `.env` file or export them directly in your shell:

```bash
DISCORD_BOT_TOKEN=your_discord_token_here
POKEMON_TCG_API_KEY=your_pokemon_tcg_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

Build and run the images:
```bash
./tools/build-images.sh
docker compose up -d 
```
