import json
import os
import time
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE = "https://api.pokemontcg.io/v2"
PAGE_SIZE = 250

API_KEY = os.getenv("POKEMON_TCG_API_KEY")
HEADERS = {"X-Api-Key": API_KEY} if API_KEY else {}

SCRIPT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "app", "data")
os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

session = requests.Session()
retries = Retry(
    total=3,
    connect=3,
    backoff_factor=1,
    status_forcelist=[404, 429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)


def fetch_paginated(endpoint: str):
    logger.info(f"Fetching paginated data from '{endpoint}'...")
    all_items = []
    page = 1

    while True:
        logger.info(f"  → Requesting page {page}...")

        try:
            resp = session.get(
                f"{API_BASE}/{endpoint}",
                params={"page": page, "pageSize": PAGE_SIZE , "select": "id,name,supertype,subtypes,types,rarity,set,number,images"},
                headers=HEADERS,
            )
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404 and page > 1:
                logger.info(f"    Page {page} returned 404 — assuming end of pages.")
                break
            logger.error(f"    HTTP error on page {page}: {e}")
            raise

        resp_json = resp.json()

        if page == 1:
            total_count = resp_json.get("totalCount", "unknown")
            logger.info(f"    Total count reported: {total_count}")

        data = resp_json.get("data", [])
        if not data:
            logger.info(f"    No data on page {page} — stopping.")
            break

        all_items.extend(data)
        logger.info(f"    Collected {len(all_items)} total items so far...")

        page += 1
        time.sleep(0.1)

    logger.info(f"Done fetching '{endpoint}' — total {len(all_items)} items.")
    return all_items


def fetch_enums():
    logger.info("Fetching enums: types, supertypes, subtypes, rarities...")
    enums = {}
    for key in ["types", "supertypes", "subtypes", "rarities"]:
        logger.info(f"  → Fetching {key}...")
        resp = session.get(f"{API_BASE}/{key}", headers=HEADERS)
        resp.raise_for_status()
        enums[key] = resp.json()["data"]
        logger.info(f"    {key}: {len(enums[key])} items.")
    logger.info("Done fetching enums.")
    return enums


def fetch_sets():
    logger.info("Fetching sets...")
    resp = session.get(f"{API_BASE}/sets", headers=HEADERS)
    resp.raise_for_status()
    sets = resp.json()["data"]
    logger.info(f"Done fetching sets: {len(sets)} items.")
    return sets


def save_json(data, filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved {filename} to {path} ({len(data)} items)")


def main():
    logger.info("Starting fetch_cards.py...")
    logger.info(f"Output directory: {DATA_DIR}")
    cards = fetch_paginated("cards")
    sets = fetch_sets()
    enums = fetch_enums()

    save_json(cards, "cards.json")
    save_json(sets, "sets.json")
    save_json(enums, "enums.json")
    logger.info("All data fetched and saved successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"ERROR: {e}")
        raise