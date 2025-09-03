import json
import logging
import os
from pathlib import Path

import discord
import pandas as pd
from discord import Interaction, app_commands
from discord.ext import commands
from openai import OpenAI as RawOpenAI
from pandasai import Agent
from pandasai.llm.openai import OpenAI

from bot.utils.logging_utils import inject_log_context, log_time

logger = logging.getLogger(__name__)
DATA_DIR = Path("/app/data")
MAX_CHARACTERS = 1800
MAX_AGENT_RESULT_ROWS = 500


def chunk_text(text: str, max_len: int = MAX_CHARACTERS) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        if end < len(text) and not text[end].isspace():
            while end > start and not text[end - 1].isspace():
                end -= 1
            if end == start:
                end = start + max_len 

        chunks.append(text[start:end].rstrip())
        start = end
        while start < len(text) and text[start].isspace():
            start += 1  
    return chunks

class AgentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        with open(DATA_DIR / "cards.json", "r", encoding="utf-8") as f:
            cards_data = json.load(f)

        with open(DATA_DIR / "enums.json", "r", encoding="utf-8") as f:
            enums = json.load(f)

        df = pd.json_normalize(cards_data, sep="_")

        for col in df.columns:
            if df[col].dtype == object:
                sample = (
                    df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                )
                if isinstance(sample, (list, dict)):
                    df[col] = df[col].apply(
                        lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
                    )

        set_names = sorted(df["set_name"].dropna().unique())
        set_names_text = "\n- " + "\n- ".join(set_names)

        def format_enum_block(title: str, values: list[str]) -> str:
            return (
                f"**Allowed {title}:**\n"
                + "\n".join(f"• {v}" for v in sorted(values))
                + "\n"
            )

        enum_text = (
            format_enum_block("Types", enums.get("types", []))
            + format_enum_block("Supertypes", enums.get("supertypes", []))
            + format_enum_block("Subtypes", enums.get("subtypes", []))
            + format_enum_block("Rarities", enums.get("rarities", []))
        )

        self.description_text = (
            "This DataFrame contains Pokémon cards, one per row.\n\n"
            "Allowed columns you can use:\n"
            "- name, supertype, subtypes, types, rarity, number\n"
            "- set_name, set_series, set_total, set_printedTotal\n"
            "- set_releaseDate, set_ptcgoCode\n"
            "- set_legalities_unlimited, set_legalities_expanded\n"
            "- images_small, images_large\n\n"
            "Only use those fields. Ignore all others.\n"
            "You may filter using fuzzy text matching by checking if a string is contained in a column (e.g., set_name).\n"
            "Always filter by set_name instead of set ID.\n"
            "Group by set_name to count cards, or search for names containing keywords like 'Pikachu'.\n\n"
            "**You must only use set_name, rarity, type, supertype, and subtype values from the lists below. Never guess or make up a value.**\n"
            f"\n**Valid set_name values:**\n{set_names_text}\n\n"
            f"{enum_text}\n"
            "Example row:\n"
            "id: example-set-001\n"
            "name: Examplemon\n"
            "supertype: Pokémon\n"
            'subtypes: ["Basic"]\n'
            'types: ["Fire"]\n'
            "number: 25\n"
            "rarity: Rare\n"
            "set_name: Sample Set\n"
            "set_series: Sample Series\n"
            "set_printedTotal: 100\n"
            "set_total: 120\n"
            "set_ptcgoCode: SAM\n"
            "set_releaseDate: 2023-01-01\n"
            "set_legalities_unlimited: Legal\n"
            "set_legalities_expanded: Legal\n"
            "images_small: [link to small image]\n"
            "images_large: [link to large image]\n\n"
            "Sample questions and how to answer them:\n"
            "- Q: Which sets contain a Pikachu?\n"
            "  → Use `.str.contains()` on the card name, then group by set:\n"
            "    df[df['name'].str.contains('Pikachu', case=False, na=False)]['set_name'].value_counts()\n\n"
            "- Q: What are the legalities of cards in Paldean Fates?\n"
            "  → Use `set_name`: **'Paldean Fates'**, then:\n"
            "    df[df['set_name'] == 'Paldean Fates'][['name', 'set_legalities_unlimited', 'set_legalities_expanded']].drop_duplicates()\n\n"
            "- Q: How many cards are in each set?\n"
            "  → Group by set name and count:\n"
            "    df.groupby('set_name')['name'].count().sort_values(ascending=False)\n\n"
            "- Q: Which set is the oldest, and what are its cards’ images?\n"
            "  → Sort by `set_releaseDate`, then select that set's images:\n"
            "    oldest_set = df.sort_values('set_releaseDate').iloc[0]['set_name']\n"
            "    df[df['set_name'] == oldest_set][['name', 'images_large']]\n\n"
            "- Q: List all Rare cards in set 151.\n"
            "  → Match `set_name`: **'Scarlet & Violet—151'**, and filter `rarity == 'Rare'`:\n"
            "    df[(df['set_name'] == 'Scarlet & Violet—151') & (df['rarity'] == 'Rare')][['name', 'rarity']]\n\n"
            "- Q: Find all cards with 'Charizard' in their name.\n"
            "  → Use `.str.contains()` filter on name:\n"
            "    df[df['name'].str.contains('Charizard', case=False, na=False)][['name', 'set_name', 'rarity']]\n\n"
            "- Q: What are the Pikachu cards in the base set?\n"
            "  → Match 'base' to the correct `set_name`: **'Base'**, then:\n"
            "    df[df['name'].str.contains('Pikachu', case=False, na=False) & (df['set_name'] == 'Base')][['name', 'set_name', 'images_large']]\n\n"
            "- Q: Show me Charizard cards in base set 2\n"
            "  → Use `set_name`: **'Base Set 2'**, then:\n"
            "    df[df['name'].str.contains('Charizard', case=False, na=False) & (df['set_name'] == 'Base Set 2')]\n\n"
            "- Q: Find cards in Hidden Fates shiny vault\n"
            "  → Use `set_name`: **'Hidden Fates Shiny Vault'**, then:\n"
            "    df[df['set_name'] == 'Hidden Fates Shiny Vault']\n\n"
            "- Q: What cards are in HS Triumphant?\n"
            "  → Use `set_name`: **'HS—Triumphant'**, then:\n"
            "    df[df['set_name'] == 'HS—Triumphant']\n\n"
            "- Q: What are the legalities of cards in FireRed & LeafGreen?\n"
            "  → Use `set_name`: **'FireRed & LeafGreen'**, then:\n"
            "    df[df['set_name'] == 'FireRed & LeafGreen']['set_legalities_expanded'].unique()\n\n"
            "- Q: Show all McDonald's promo cards\n"
            "  → Use `set_name`: **'McDonald's Collection 2019'**, then:\n"
            "    df[df['set_name'] == \"McDonald's Collection 2019\"]\n\n"
            "Do not use or refer to any system-level operations or modules. Stick to analyzing the DataFrame using text and filters."
        )

        self.llm = OpenAI(api_token=os.getenv("OPENAI_API_KEY"))
        self.format_llm = RawOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.agent = Agent(
            df,
            config={
                "llm": self.llm,
                "verbose": True,
                "enable_cache": False,
                "save_logs": True,
                "security": "low",
            },
        )

    @app_commands.command(
        name="agent", description="Ask the Pokémon TCG agent a question."
    )
    @inject_log_context
    @log_time(logger.info)
    async def ask_agent(self, interaction: Interaction, question: str):
        await interaction.response.defer()
        try:
            full_prompt = f"""{self.description_text}\n\nNow answer this: {question}"""
            raw_result = self.agent.chat(full_prompt)

            if isinstance(raw_result, pd.DataFrame):
                total_rows = len(raw_result)

                if total_rows > MAX_AGENT_RESULT_ROWS:
                    await interaction.followup.send(
                        f"🔎 Truncating agent result to {MAX_AGENT_RESULT_ROWS} rows from {total_rows} rows."
                    )
                    raw_result = raw_result.head(100)

                content = raw_result.to_markdown(index=False)
            else:
                content = str(raw_result).strip()

            prompt = (
                "You're a Discord bot that formats answers from a Pokémon Trading Card Game (TCG) data agent.\n\n"
                "Strict rules:\n"
                "- Only reference Pokémon TCG. Never mention Magic: The Gathering, Yu-Gi-Oh!, or any other franchise.\n"
                "- Do not guess or fabricate information.\n"
                "- The user question and the agent's raw output are always about Pokémon cards or sets.\n\n"
                "Formatting rules:\n"
                "- Use bold for section headers and important numbers.\n"
                "- Use bullet points or emoji bullets (• or ➤) for lists.\n"
                "- Separate sections with clear spacing.\n"
                "- Keep messages phone-readable (short lines, logical spacing).\n"
                "- If the result is a table, format each row like a labeled block.\n"
                "- Only show the **large card image** if available — do **not** show or link the small image.\n"
                "- Never add your own commentary. Just format the output cleanly.\n"
                "- **Do NOT add 'Answer:' or restate the question.** The question is already included in the final message.\n\n"
                "Here are some EXAMPLES of correct formatting:\n\n"
                "**Q: How many cards are in each set?**\n"
                "**Set Totals:**\n"
                "• Paldean Fates → 230 cards\n"
                "• 151 → 165 cards\n"
                "• Obsidian Flames → 210 cards\n\n"
                "**Q: What are the legalities of cards in set 'Scarlet & Violet'?**\n"
                "➤ **Scarlet & Violet**\n"
                "• Unlimited: Legal\n"
                "• Expanded: Legal\n\n"
                "**Q: Find all cards with 'Charizard' in their name.**\n"
                "**Charizard Cards Found:**\n"
                "• Charizard ex (Obsidian Flames)\n"
                "• Dark Charizard (Team Rocket)\n"
                "• Radiant Charizard (Crown Zenith)\n"
                "• Charizard VMAX (Champion’s Path)\n\n"
                "**Q: Show me all cards in set '151' that are Rare.**\n"
                "➤ **Set: 151**\n"
                "• Mew ex – Rare\n"
                "• Alakazam – Rare\n"
                "• Zapdos – Rare\n\n"
                f"The user asked:\n**{question}**\n\n"
                "Here is the agent's raw output:\n"
                f"```\n{content}\n```\n\n"
                "Now format that raw output according to the rules and examples above."
            )


            response = self.format_llm.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You're a helpful Discord bot formatter.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            formatted = response.choices[0].message.content.strip()
            chunks = chunk_text(formatted)

            await interaction.followup.send(f"**Q:** {question}\n{chunks[0]}")
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)

        except Exception as e:
            logger.exception("Agent query failed")
            await interaction.followup.send(f"❌ Error: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AgentCog(bot))
