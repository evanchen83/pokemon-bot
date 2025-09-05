import os
import json
from psycopg_pool import ConnectionPool

DB_POOL = ConnectionPool(
    conninfo=(
        f"host={os.getenv('DB_HOST', 'localhost')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'cards')} "
        f"user={os.getenv('DB_USER', 'postgres')} "
        f"password={os.getenv('DB_PASSWORD', 'postgres')}"
    ),
    min_size=1,
    max_size=10,
)

def get_cards(discord_id: str) -> dict[str, int]:
    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cards FROM player_cards WHERE discord_id = %s",
                (discord_id,),
            )
            row = cur.fetchone()
            return row[0] if row else {}

def add_cards(discord_id: str, cards_to_add: dict[str, int]) -> None:
    with DB_POOL.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (discord_id,),
                )

                cur.execute(
                    "SELECT cards FROM player_cards WHERE discord_id = %s",
                    (discord_id,),
                )
                row = cur.fetchone()
                current_cards: dict[str, int] = row[0] if row else {}

                for card_id, count in cards_to_add.items():
                    current_cards[card_id] = current_cards.get(card_id, 0) + count

                cur.execute(
                    """
                    INSERT INTO player_cards (discord_id, cards)
                    VALUES (%s, %s)
                    ON CONFLICT (discord_id) DO UPDATE
                    SET cards = EXCLUDED.cards
                    """,
                    (discord_id, json.dumps(current_cards)),
                )

def remove_cards(discord_id: str, cards_to_remove: dict[str, int]) -> None:
    with DB_POOL.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (discord_id,),
                )

                cur.execute(
                    "SELECT cards FROM player_cards WHERE discord_id = %s",
                    (discord_id,),
                )
                row = cur.fetchone()
                current_cards: dict[str, int] = row[0] if row else {}

                for card_id, count in cards_to_remove.items():
                    if card_id not in current_cards:
                        raise ValueError(f"User does not own card: {card_id}")
                    if current_cards[card_id] < count:
                        raise ValueError(
                            f"User has only {current_cards[card_id]} of card {card_id}, "
                            f"cannot remove {count}"
                        )

                    current_cards[card_id] -= count
                    if current_cards[card_id] == 0:
                        del current_cards[card_id]

                cur.execute(
                    """
                    INSERT INTO player_cards (discord_id, cards)
                    VALUES (%s, %s)
                    ON CONFLICT (discord_id) DO UPDATE
                    SET cards = EXCLUDED.cards
                    """,
                    (discord_id, json.dumps(current_cards)),
                )
