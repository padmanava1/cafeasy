"""
Data Synthesis and Augmentation Engine for Cafeasy
Generates and enriches 1,000+ realistic, high-quality, geographically accurate
cafes and dining establishments distributed across 26 major Ahmedabad neighborhoods.
All records are strictly validated against Pydantic models before persisting.
"""

import sys
import json
import random
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.models import Cafe

# Locality definitions with center GPS coordinates and dispersion radii
NEIGHBORHOODS = [
    {"name": "Sindhu Bhavan Road", "lat": 23.0465, "lng": 72.5065, "radius": 0.012, "vibe_bias": ["Upscale", "Modern", "Late Night", "Specialty Coffee"]},
    {"name": "Bodakdev", "lat": 23.0410, "lng": 72.5190, "radius": 0.010, "vibe_bias": ["Work Friendly", "Date Night", "Specialty Coffee"]},
    {"name": "Vastrapur", "lat": 23.0360, "lng": 72.5320, "radius": 0.009, "vibe_bias": ["Student Friendly", "Budget", "Quiet", "Chai"]},
    {"name": "Satellite", "lat": 23.0255, "lng": 72.5260, "radius": 0.010, "vibe_bias": ["Family Friendly", "Pure Veg", "Desserts"]},
    {"name": "Prahlad Nagar", "lat": 23.0130, "lng": 72.5110, "radius": 0.011, "vibe_bias": ["Corporate", "Work Friendly", "Italian", "Date Night"]},
    {"name": "Thaltej", "lat": 23.0645, "lng": 72.5135, "radius": 0.012, "vibe_bias": ["Garden Seating", "Rooftop", "Continental"]},
    {"name": "Bopal", "lat": 23.0340, "lng": 72.4720, "radius": 0.014, "vibe_bias": ["Budget", "Chai", "Casual Hangout", "Pure Veg"]},
    {"name": "South Bopal", "lat": 23.0240, "lng": 72.4640, "radius": 0.012, "vibe_bias": ["Youth Hangout", "Fast Food", "Late Night"]},
    {"name": "Ambawadi", "lat": 23.0225, "lng": 72.5480, "radius": 0.008, "vibe_bias": ["Heritage", "Quiet", "Specialty Coffee"]},
    {"name": "Navrangpura", "lat": 23.0385, "lng": 72.5560, "radius": 0.010, "vibe_bias": ["Student Friendly", "Reading", "Chai", "Late Night"]},
    {"name": "CG Road", "lat": 23.0325, "lng": 72.5620, "radius": 0.008, "vibe_bias": ["Shopping", "Desserts", "Italian", "Pure Veg"]},
    {"name": "Law Garden", "lat": 23.0245, "lng": 72.5630, "radius": 0.007, "vibe_bias": ["Street Food", "Chai", "Pure Veg", "Budget"]},
    {"name": "Usmanpura", "lat": 23.0470, "lng": 72.5710, "radius": 0.009, "vibe_bias": ["Business", "Fast Casual", "Continental"]},
    {"name": "Paldi", "lat": 23.0120, "lng": 72.5610, "radius": 0.010, "vibe_bias": ["Pure Veg", "Jain Friendly", "Heritage Thali"]},
    {"name": "Sabarmati Riverfront", "lat": 23.0310, "lng": 72.5790, "radius": 0.010, "vibe_bias": ["Scenic View", "Date Night", "Open Air"]},
    {"name": "Lal Darwaja", "lat": 23.0250, "lng": 72.5860, "radius": 0.008, "vibe_bias": ["Heritage", "Traditional", "Street Food", "Tea"]},
    {"name": "Manek Chowk", "lat": 23.0220, "lng": 72.5930, "radius": 0.006, "vibe_bias": ["Late Night", "Street Food", "Desserts", "Pure Veg"]},
    {"name": "Shahibaug", "lat": 23.0650, "lng": 72.5960, "radius": 0.011, "vibe_bias": ["Family Friendly", "Traditional", "Pure Veg"]},
    {"name": "Chandkheda", "lat": 23.1110, "lng": 72.5860, "radius": 0.013, "vibe_bias": ["Casual Hangout", "Fast Food", "Coffee"]},
    {"name": "Motera", "lat": 23.0960, "lng": 72.5990, "radius": 0.012, "vibe_bias": ["Sports Cafe", "Late Night", "Burgers & Pizza"]},
    {"name": "Gota", "lat": 23.1060, "lng": 72.5360, "radius": 0.014, "vibe_bias": ["Budget", "Chai", "Casual Hangout"]},
    {"name": "Science City Road", "lat": 23.0820, "lng": 72.5080, "radius": 0.012, "vibe_bias": ["Rooftop", "Family Friendly", "Continental"]},
    {"name": "Maninagar", "lat": 22.9985, "lng": 72.6060, "radius": 0.011, "vibe_bias": ["Lakeside", "Pure Veg", "South Indian", "Desserts"]},
    {"name": "Nikol", "lat": 23.0460, "lng": 72.6560, "radius": 0.013, "vibe_bias": ["Kathiyawadi", "Pure Veg", "Chai", "Fast Food"]},
    {"name": "Naroda", "lat": 23.0760, "lng": 72.6610, "radius": 0.014, "vibe_bias": ["Family Dining", "Budget", "Pure Veg"]},
    {"name": "Vastral", "lat": 23.0060, "lng": 72.6510, "radius": 0.013, "vibe_bias": ["Street Eats", "Casual", "Budget"]}
]

# Name generator patterns
PREFIXES = [
    "The Roasted", "Cafe", "Brew &", "Urban", "The Little", "Artisan", "Bean &",
    "Mocha", "Coffee", "Velvet", "The Rustic", "Crust &", "Bake &", "The Daily",
    "Amber", "Chai &", "Chai", "The Secret", "Soul", "The Green", "Wood &",
    "Aroma", "Sugar &", "Bistro", "The Hidden", "Flavours of", "Saffron", "Heritage",
    "Kettle &", "Cup &", "The Social", "Waffle &", "Dough &", "Casa", "Terra",
    "Bella", "Cielo", "Gourmet", "The Courtyard", "Roastery", "Steam &", "The Loft",
    "Nomad", "Zenith", "Spiced", "Boutique", "The Yellow", "Golden", "Pure", "Royal"
]

NOUNS = [
    "Bean", "Grind", "Leaf", "Roast", "Bistro", "Table", "Corner", "Loft", "Nook",
    "Lounge", "Hub", "Junction", "Haven", "Terrace", "Kitchen", "Atelier", "Brewery",
    "Garden", "Diner", "Spot", "Yard", "Bakehouse", "Craft", "Square", "Lane",
    "Roots", "Room", "Tree", "Palette", "Plate", "Story", "Blend", "Espresso",
    "Bakery", "Pot", "Cup", "Station", "Boutique", "Cottage", "Bay", "Perk"
]

CUISINE_POOLS = [
    ["Specialty Coffee", "Italian", "Desserts"],
    ["Continental", "Cafe", "Italian"],
    ["Specialty Coffee", "Bakery", "Breakfast"],
    ["Chai", "Street Food", "Fast Food"],
    ["Gujarati", "Kathiyawadi", "Traditional"],
    ["Italian & Pizza", "Pasta", "Beverages"],
    ["Mexican", "Continental", "Fast Food"],
    ["Desserts", "Bakery", "Waffles"],
    ["Asian", "Continental", "Cafe"],
    ["Healthy Food", "Salads", "Coffee"]
]

MUST_TRY_POOLS = [
    ["Single Origin Pour-over", "Truffle Fries", "Avocado Sourdough Toast"],
    ["Wood-fired Margherita Pizza", "Classic Tiramisu", "Cold Brew Tonic"],
    ["Iced Cinnamon Latte", "Nutella Stuffed Croissant", "Pesto Panini"],
    ["Masala Kulhad Chai", "Cheese Chilli Toast", "Butter Bun Maska"],
    ["Gujarati Gourmet Thali", "Khaman Chaat", "Kesar Shrikhand"],
    ["Four Cheese Wood-fired Pizza", "Creamy Alfredo Penne", "Belgian Chocolate Shake"],
    ["Overnight Cold Brew", "Blueberry Cheesecake", "Garlic Butter Bagel"],
    ["Mexican Chimichanga", "Loaded Nachos", "Virgin Mojito"],
    ["Sizzling Brownie with Ice Cream", "Lotus Biscoff Waffle", "Hot Chocolate"],
    ["Espresso Tonic", "Falafel Mezze Platter", "Smoked Paneer Wrap"],
    ["Irani Chai", "Bun Maska with Mava Cake", "Anda Ghotala Special"],
    ["Dark Chocolate Sea Salt Tart", "Cortado", "Sun-dried Tomato Bruschetta"]
]

TAG_POOLS = [
    ["Work Friendly", "High Speed Wi-Fi", "Specialty Coffee", "Quiet"],
    ["Date Night", "Romantic", "Candlelit", "Outdoor Seating"],
    ["Late Night", "24/7", "Youth Hangout", "Casual"],
    ["Pure Veg", "Jain Friendly", "Family Friendly"],
    ["Rooftop", "Open Air", "Sunset View", "Romantic"],
    ["Board Games", "Social", "Group Friendly", "Student Friendly"],
    ["Cozy", "Book Reading", "Quiet", "Artisanal"],
    ["Budget Friendly", "Pocket Friendly", "Street Food", "Quick Bites"],
    ["Pet Friendly", "Garden Seating", "Live Music"],
    ["Aesthetic", "Instagrammable", "Specialty Desserts", "Date Night"]
]

STREET_TYPES = [
    "Main Road", "Avenue", "Crossroads", "Lane", "Boulevard", "Circle", "High Street",
    "Commercial Complex", "Business Park", "Heritage Precinct", "Plaza", "Hub"
]


def generate_venue_name(existing_names: set) -> str:
    """Generates an authentic and distinct venue name."""
    for _ in range(50):
        p = random.choice(PREFIXES)
        n = random.choice(NOUNS)
        name = f"{p} {n}"
        if name not in existing_names:
            return name
        # Variant
        name2 = f"{p} {n} Co."
        if name2 not in existing_names:
            return name2
    # Fallback
    return f"Cafe {random.choice(NOUNS)} {random.randint(10, 999)}"


def build_1000_venues(existing_venues: List[Dict[str, Any]], target_total: int = 1050) -> List[Dict[str, Any]]:
    existing_names = set(v["name"] for v in existing_venues)
    venues = list(existing_venues)
    current_count = len(venues)
    needed = target_total - current_count

    print(f"Starting generation: {current_count} existing venues, targeting {target_total} (generating {needed} new venues)...")

    venue_id_counter = 100

    for i in range(needed):
        neighborhood = random.choice(NEIGHBORHOODS)
        name = generate_venue_name(existing_names)
        existing_names.add(name)

        # Coordinate calculation with realistic gaussian distribution around neighborhood hub
        lat_offset = random.gauss(0, neighborhood["radius"] * 0.5)
        lng_offset = random.gauss(0, neighborhood["radius"] * 0.5)
        lat = round(neighborhood["lat"] + lat_offset, 5)
        lng = round(neighborhood["lng"] + lng_offset, 5)

        # Realistic rating distribution (3.9 - 4.9)
        rating = round(random.triangular(3.9, 4.9, 4.5), 1)

        # Pricing distribution (INR for two)
        price_tier = random.choices([400, 600, 800, 1100, 1500, 2000], weights=[20, 30, 25, 15, 7, 3])[0]
        price_for_two = int(price_tier + random.randint(-50, 50))

        # Dietary distribution: Ahmedabad is heavily vegetarian
        dietary = random.choices(["Pure Veg", "Jain Friendly", "Veg & Non-Veg"], weights=[65, 20, 15])[0]

        # Select cuisine & dishes
        cuisines = random.choice(CUISINE_POOLS)
        must_tries = random.choice(MUST_TRY_POOLS)
        tags = list(random.choice(TAG_POOLS))

        if dietary == "Pure Veg" and "Pure Veg" not in tags:
            tags.append("Pure Veg")
        if dietary == "Jain Friendly":
            if "Pure Veg" not in tags:
                tags.append("Pure Veg")
            if "Jain Friendly" not in tags:
                tags.append("Jain Friendly")

        vibe_bias = neighborhood["vibe_bias"]
        extra_tag = random.choice(vibe_bias)
        if extra_tag not in tags:
            tags.append(extra_tag)

        # Address
        street = random.choice(STREET_TYPES)
        bldg_no = random.randint(1, 99)
        floor = random.choice(["Ground Floor", "1st Floor", "Rooftop", "Mezzanine Floor", "GF & 1F"])
        address = f"Shop {bldg_no}, {floor}, {neighborhood['name']} {street}, {neighborhood['name']}, Ahmedabad - 3800{random.randint(15, 60)}"

        # Deterministic Google Maps URL
        gmaps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

        # Highlights & Review summary
        highlight_templates = [
            f"Vibrant contemporary cafe in {neighborhood['name']} featuring {', '.join(cuisines[:2])} with welcoming vibes.",
            f"Charming neighborhood retreat in {neighborhood['name']} popular for {must_tries[0]} and cozy indoor/outdoor ambience.",
            f"Artisanal culinary spot in the heart of {neighborhood['name']}, known for handcrafted brews, {tags[0].lower()} atmosphere, and warm hospitality.",
            f"Sleek and inviting dining space on {neighborhood['name']} offering {dietary.lower()} delicacies, ergonomic seating, and pleasant music.",
            f"Scenic hotspot in {neighborhood['name']} with {tags[1] if len(tags) > 1 else 'great'} seating, ideal for casual catchups and signature dishes."
        ]
        highlights = random.choice(highlight_templates)

        review_templates = [
            f"Patrons frequently praise the {must_tries[0]} and {must_tries[1]}. Rated {rating} for courteous service and great value.",
            f"Known for authentic flavours, quick table service, and soothing ambiance. Highly recommended for {tags[0].lower()}.",
            f"Customers love the relaxed vibe, consistent food quality, and delicious {must_tries[0]}. A favorite in {neighborhood['name']}.",
            f"Praised by locals for hygienic preparations, ample seating, and exceptional {cuisines[0].lower()} offerings."
        ]
        review_summary = random.choice(review_templates)

        venue_id = f"cafe-ahd-{venue_id_counter:04d}"
        venue_id_counter += 1

        cafe_dict = {
            "id": venue_id,
            "name": name,
            "area": neighborhood["name"],
            "address": address,
            "lat": lat,
            "lng": lng,
            "price_for_two": price_for_two,
            "rating": rating,
            "tags": tags[:5],
            "cuisine": cuisines,
            "dietary": dietary,
            "must_try_dishes": must_tries,
            "highlights": highlights,
            "review_summary": review_summary,
            "google_maps_url": gmaps_url
        }

        venues.append(cafe_dict)

    return venues


def main():
    data_path = Path(__file__).resolve().parent.parent / "data" / "ahmedabad_cafes.json"
    
    with open(data_path, "r", encoding="utf-8") as f:
        existing = json.load(f)

    print(f"Loaded {len(existing)} existing cafes from {data_path.name}")

    all_venues = build_1000_venues(existing, target_total=1035)

    # Validate all generated venues using Pydantic
    print("Validating all venues through Pydantic model...")
    validated_list = []
    for idx, v in enumerate(all_venues):
        try:
            validated = Cafe(**v)
            validated_list.append(validated.model_dump())
        except Exception as e:
            print(f"Validation failed on item {idx} ({v.get('name')}): {e}")

    print(f"Successfully validated {len(validated_list)} venues!")

    # Write back to JSON
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(validated_list, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(validated_list)} verified venues to {data_path}!")


if __name__ == "__main__":
    main()
