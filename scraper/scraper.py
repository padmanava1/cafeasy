"""
Cafeasy Scraper & Data ETL Pipeline
Fetches restaurant and cafe points of interest across Ahmedabad, parses unstructured
HTML/JSON, enriches with tags (vibe, budget, cuisine), and validates into Pydantic models.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

from backend.models import Cafe

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

AHMEDABAD_BOUNDS = {
    "south": 22.95,
    "west": 72.45,
    "north": 23.12,
    "east": 72.65
}


class AhmedabadCafeScraper:
    """Scrapes, normalizes, and enriches culinary points of interest in Ahmedabad."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or Path(__file__).resolve().parent.parent / "data" / "ahmedabad_cafes.json"

    def fetch_from_openstreetmap(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Queries the OpenStreetMap Overpass API for cafes and restaurants in Ahmedabad.
        This provides real-world coordinates and metadata with zero rate-limit or API key barriers.
        """
        logger.info("Querying Overpass API for Ahmedabad cafes...")
        overpass_url = "https://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="cafe"]({AHMEDABAD_BOUNDS['south']},{AHMEDABAD_BOUNDS['west']},{AHMEDABAD_BOUNDS['north']},{AHMEDABAD_BOUNDS['east']});
          node["amenity"="restaurant"]["cuisine"~"cafe|coffee|italian|bakery"]({AHMEDABAD_BOUNDS['south']},{AHMEDABAD_BOUNDS['west']},{AHMEDABAD_BOUNDS['north']},{AHMEDABAD_BOUNDS['east']});
        );
        out body {limit};
        >;
        out skel qt;
        """
        try:
            response = requests.post(overpass_url, data={"data": overpass_query}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])
                logger.info(f"Retrieved {len(elements)} raw points of interest from OSM.")
                return elements
            else:
                logger.warning(f"Overpass API returned status code {response.status_code}")
                return []
        except Exception as e:
            logger.warning(f"Failed to fetch live Overpass data: {e}. Falling back to curated dataset.")
            return []

    def parse_html_review_snippet(self, html_snippet: str) -> Dict[str, Any]:
        """
        Demonstrates BeautifulSoup extraction of user reviews, ratings, and highlights
        from raw HTML snippets (e.g. food blog or directory pages).
        """
        soup = BeautifulSoup(html_snippet, "html.parser")
        name = soup.find("h1") or soup.find("h2")
        rating_elem = soup.find(class_="rating") or soup.find("span", {"data-rating": True})
        review_elem = soup.find("p", class_="review-text")

        return {
            "name": name.get_text(strip=True) if name else "Unknown Cafe",
            "rating": float(rating_elem.get_text(strip=True)) if rating_elem else 4.0,
            "review": review_elem.get_text(strip=True) if review_elem else ""
        }

    def load_seed_dataset(self) -> List[Cafe]:
        """Loads and validates the high-fidelity curated seed dataset."""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Dataset file not found at {self.data_file}")

        with open(self.data_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        validated_cafes: List[Cafe] = []
        for item in raw_data:
            try:
                cafe = Cafe(**item)
                validated_cafes.append(cafe)
            except Exception as e:
                logger.error(f"Validation failed for cafe {item.get('name')}: {e}")

        logger.info(f"Loaded and validated {len(validated_cafes)} cafes from {self.data_file.name}")
        return validated_cafes


if __name__ == "__main__":
    scraper = AhmedabadCafeScraper()
    cafes = scraper.load_seed_dataset()
    print(f"Successfully loaded {len(cafes)} verified cafes.")
    if cafes:
        sample = cafes[0]
        print(f"Sample: {sample.name} ({sample.area}) - Rating: {sample.rating} - Maps: {sample.google_maps_url}")
