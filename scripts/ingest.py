"""
Cafeasy Ingestion Script
Loads ahmedabad_cafes.json, validates schemas, and indexes all documents into ChromaDB.
"""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from scraper.scraper import AhmedabadCafeScraper
from rag.vector_store import CafeVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("--- Starting Cafeasy Knowledge Ingestion ---")
    scraper = AhmedabadCafeScraper()
    cafes = scraper.load_seed_dataset()
    logger.info(f"Loaded {len(cafes)} verified cafes from dataset.")

    vector_store = CafeVectorStore()
    total_indexed = vector_store.ingest_cafes(cafes, force_refresh=True)

    logger.info(f"--- Ingestion Complete! Total indexed in ChromaDB: {total_indexed} ---")

    # Quick verification query
    logger.info("Executing sample hybrid verification query: 'romantic date night in Bodakdev'")
    results = vector_store.hybrid_search("romantic date night in Bodakdev", n_results=2)
    for i, res in enumerate(results, 1):
        logger.info(f"Top {i}: {res['name']} ({res['area']}) - Rating: {res['rating']} - Maps: {res['google_maps_url']}")


if __name__ == "__main__":
    main()
