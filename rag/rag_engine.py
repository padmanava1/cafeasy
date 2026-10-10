"""
Cafeasy Advanced RAG Engine & Conversational Synthesizer
Features:
- Two-Stage Retrieval with Semantic Vector Search + Heuristic/Cross-Attribute Re-Ranking
- Multi-Turn Conversational Memory per session
- Haversine Proximity Calculation & Turn-by-Turn Navigation URLs
- Multi-Criteria Filtering (Dietary: Pure Veg/Jain/Non-Veg, Vibe, Cuisine, Budget, Distance)
- Grounded Synthesis with Gemini 3.8 Flash & Resilient Fallback
"""

import os
import re
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

from backend.models import Cafe, QueryRequest, QueryResponse, GeoPoint
from rag.vector_store import CafeVectorStore

load_dotenv()
logger = logging.getLogger(__name__)

# Known Ahmedabad locality aliases
LOCALITY_MAP = {
    "sbr": "Sindhu Bhavan Road",
    "sindhu bhavan": "Sindhu Bhavan Road",
    "sindhu bhavan road": "Sindhu Bhavan Road",
    "bodakdev": "Bodakdev",
    "judges bungalow": "Bodakdev",
    "vastrapur": "Vastrapur",
    "iim": "Vastrapur",
    "navrangpura": "Navrangpura",
    "cg road": "CG Road",
    "c.g. road": "CG Road",
    "prahlad nagar": "Prahlad Nagar",
    "prahladnagar": "Prahlad Nagar",
    "satellite": "Satellite",
    "ambawadi": "Ambawadi",
    "lal darwaja": "Lal Darwaja",
    "old city": "Lal Darwaja",
    "sabarmati": "Sabarmati Riverfront",
    "riverfront": "Sabarmati Riverfront",
    "paldi": "Paldi",
    "gandhinagar": "Gandhinagar Highway",
    "sg highway": "Bodakdev",
    "s.g. highway": "Bodakdev"
}


def calculate_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class CafeasyRAGEngine:
    """End-to-end RAG orchestrator with multi-turn memory and two-stage ranking."""

    def __init__(self, vector_store: Optional[CafeVectorStore] = None):
        self.vector_store = vector_store or CafeVectorStore()
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self._gemini_client = None
        # Conversational memory: session_id -> list of {"role": "user"|"assistant", "text": str}
        self.sessions: Dict[str, List[Dict[str, str]]] = {}

        if self.api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.api_key)
                logger.info("Gemini API client initialized successfully with gemini-3.8-flash.")
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai client: {e}. Will use Smart Grounded Reasoner.")

    def extract_slots(self, query: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str], Optional[str], bool]:
        """
        Parses query using NLP / regex patterns to detect:
        1. Area/Locality
        2. Budget constraint
        3. Dietary preference
        4. Vibe/Ambiance
        5. Cuisine
        6. Proximity intent ('near me', 'closest', 'nearby')
        """
        lower_q = query.lower()

        # 1. Detect Area
        detected_area = None
        for alias, formal_name in LOCALITY_MAP.items():
            if re.search(rf"\b{re.escape(alias)}\b", lower_q):
                detected_area = formal_name
                break

        # 2. Detect Budget Constraint
        detected_budget = None
        budget_match = re.search(r"(?:under|below|less than|within|around)\s*(?:rs\.?|inr|₹)?\s*(\d{3,5})", lower_q)
        if budget_match:
            try:
                detected_budget = int(budget_match.group(1))
            except ValueError:
                pass
        elif "cheap" in lower_q or "budget" in lower_q:
            detected_budget = 600

        # 3. Detect Dietary
        detected_dietary = None
        if "jain" in lower_q:
            detected_dietary = "Jain Friendly"
        elif "pure veg" in lower_q or "strictly veg" in lower_q:
            detected_dietary = "Pure Veg"
        elif "non-veg" in lower_q or "non veg" in lower_q or "chicken" in lower_q:
            detected_dietary = "Veg & Non-Veg"

        # 4. Detect Vibe
        detected_vibe = None
        vibe_keywords = {
            "date": "Date Night",
            "romantic": "Date Night",
            "work": "Work Friendly",
            "laptop": "Work Friendly",
            "study": "Work Friendly",
            "quiet": "Quiet",
            "peaceful": "Quiet",
            "reading": "Quiet",
            "books": "Quiet",
            "late night": "Late Night",
            "midnight": "Late Night",
            "rooftop": "Rooftop",
            "aesthetic": "Aesthetic",
            "games": "Board Games"
        }
        for kw, v in vibe_keywords.items():
            if re.search(rf"\b{re.escape(kw)}\b", lower_q):
                detected_vibe = v
                break

        # 5. Detect Cuisine
        detected_cuisine = None
        cuisine_keywords = {
            "coffee": "Specialty Coffee",
            "espresso": "Specialty Coffee",
            "brew": "Specialty Coffee",
            "pizza": "Italian",
            "pasta": "Italian",
            "italian": "Italian",
            "chai": "Chai & Snacks",
            "tea": "Specialty Teas",
            "thali": "Gujarati Thali",
            "gujarati": "Gujarati Thali",
            "dessert": "Desserts",
            "gelato": "Desserts",
            "chocolate": "Desserts",
            "waffle": "Desserts",
            "burger": "Burgers"
        }
        for kw, c in cuisine_keywords.items():
            if re.search(rf"\b{re.escape(kw)}\b", lower_q):
                detected_cuisine = c
                break

        # 6. Detect Proximity / 'Near Me'
        is_near_me = bool(re.search(r"\b(near me|nearby|closest|around me|nearest|close to me)\b", lower_q))

        return detected_area, detected_budget, detected_dietary, detected_vibe, detected_cuisine, is_near_me

    def format_grounded_prompt(
        self,
        query: str,
        candidate_cafes: List[Dict[str, Any]],
        has_user_loc: bool = False,
        session_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Assembles strict grounding prompt with verified metadata, distances, session history, and zero-hallucination rules."""
        context_blocks = []
        for i, cafe in enumerate(candidate_cafes, 1):
            dishes = ", ".join(cafe.get("must_try_dishes", []))
            tags = ", ".join(cafe.get("tags", []))
            dist_str = f" | Distance from user: {cafe['distance_km']} km away" if cafe.get("distance_km") is not None else ""
            nav_str = f"- Turn-by-Turn Driving Navigation Link: {cafe['navigation_url']}\n" if cafe.get("navigation_url") else ""

            block = (
                f"[{i}] {cafe['name']} ({cafe['area']})\n"
                f"- Rating: {cafe['rating']}/5.0 | Approx Cost for Two: ₹{cafe['price_for_two']}{dist_str}\n"
                f"- Dietary: {cafe['dietary']} | Tags: {tags}\n"
                f"- Highlights: {cafe['highlights']}\n"
                f"- Must-Try Dishes: {dishes}\n"
                f"- Reviews Summary: {cafe['review_summary']}\n"
                f"{nav_str}"
                f"- Verified Google Maps Location: {cafe['google_maps_url']}\n"
            )
            context_blocks.append(block)

        context_str = "\n".join(context_blocks)

        history_str = ""
        if session_history and len(session_history) > 1:
            history_blocks = []
            for msg in session_history[-4:]:  # last 4 turns
                role = "User" if msg["role"] == "user" else "Cafeasy AI"
                history_blocks.append(f"{role}: {msg['text']}")
            history_str = "PREVIOUS CHAT CONVERSATION:\n" + "\n".join(history_blocks) + "\n\n"

        prompt = f"""You are Cafeasy AI, the expert dining concierge for Ahmedabad.
Recommend the best matching spots based strictly on the verified venue details below.

{history_str}USER QUERY: "{query}"

VERIFIED AHMEDABAD VENUES:
{context_str}

INSTRUCTIONS:
1. Recommend ONLY these verified venues.
2. For each venue, include:
   - Rating, Price for Two (and Distance if provided)
   - Why it matches their vibe/dietary criteria
   - Top must-try dishes
   - Direct Google Maps navigation link: [Directions on Google Maps](URL)
3. Keep the response lively, concise, and structured in Markdown.
"""
        return prompt

    def generate_recommendations(self, request: QueryRequest) -> QueryResponse:
        """
        Executes the Two-Stage Hybrid RAG Pipeline:
        1. Slot Extraction & GPS Proximity Detection
        2. Stage-1: ChromaDB Dense Semantic Search + Hard Scalar Filtering
        3. Stage-2: Heuristic & Multi-Attribute Re-Ranking (Score weighting)
        4. LLM Synthesis with Multi-Turn Memory & Grounding
        5. Structured GeoJSON points generation with Turn-by-Turn Navigation links
        """
        session_id = request.session_id or "default"
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        # Step 1: Slot Extraction
        ext_area, ext_budget, ext_dietary, ext_vibe, ext_cuisine, is_near_me = self.extract_slots(request.query)
        area = request.area or ext_area
        budget = request.max_budget or ext_budget
        dietary = request.dietary or ext_dietary
        vibe = request.vibe or ext_vibe
        cuisine = request.cuisine or ext_cuisine

        has_user_coords = request.user_lat is not None and request.user_lng is not None

        logger.info(f"Query: '{request.query}' | Slots: Area={area}, Budget={budget}, Dietary={dietary}, Vibe={vibe}, Cuisine={cuisine}, NearMe={is_near_me}")

        # Step 2: Stage-1 Vector Retrieval (Over-fetch for re-ranking)
        stage1_candidates = self.vector_store.hybrid_search(
            query=request.query,
            area=area if not is_near_me else None,
            max_budget=budget,
            dietary="Pure Veg" if dietary == "Pure Veg" else None,
            n_results=8  # Fast & focused retrieval for Stage-2 re-ranking
        )

        if not stage1_candidates:
            stage1_candidates = self.vector_store.get_all_cafes()[:8]

        # Calculate distances & Build turn-by-turn navigation URLs
        for c in stage1_candidates:
            cafe_lat = float(c["lat"])
            cafe_lng = float(c["lng"])
            if has_user_coords:
                dist = calculate_haversine_km(request.user_lat, request.user_lng, cafe_lat, cafe_lng)
                c["distance_km"] = dist
                c["navigation_url"] = f"https://www.google.com/maps/dir/?api=1&origin={request.user_lat},{request.user_lng}&destination={cafe_lat},{cafe_lng}&travelmode=driving"
            else:
                c["distance_km"] = None
                c["navigation_url"] = c["google_maps_url"]

        # Step 3: Stage-2 Candidate Filtering & Multi-Attribute Scoring
        filtered = []
        for c in stage1_candidates:
            # Filter by Jain Friendly if requested
            if dietary == "Jain Friendly":
                tags_str = " ".join(c.get("tags", [])).lower()
                hl_str = c.get("highlights", "").lower()
                if "jain" not in tags_str and "jain" not in hl_str and c.get("dietary") != "Pure Veg":
                    continue
            elif dietary == "Pure Veg" and c.get("dietary") != "Pure Veg":
                continue
            elif dietary == "Veg & Non-Veg" and c.get("dietary") != "Veg & Non-Veg":
                # soft check
                pass

            # Filter by Vibe if explicitly chosen in dropdown
            if vibe and vibe != "All Vibes":
                tags_str = " ".join(c.get("tags", [])).lower()
                hl_str = c.get("highlights", "").lower()
                if vibe.lower() not in tags_str and vibe.lower() not in hl_str:
                    continue

            # Filter by Cuisine if explicitly chosen in dropdown
            if cuisine and cuisine != "All Cuisines":
                cuisines_str = " ".join(c.get("cuisine", [])).lower()
                dishes_str = " ".join(c.get("must_try_dishes", [])).lower()
                if cuisine.lower() not in cuisines_str and cuisine.lower() not in dishes_str:
                    continue

            # Filter by Distance radius if provided
            if has_user_coords and request.max_distance_km:
                if c.get("distance_km") and c["distance_km"] > request.max_distance_km:
                    continue

            filtered.append(c)

        if not filtered:
            # If strict multi-criteria filter was too narrow, fall back to stage1 candidates
            filtered = stage1_candidates

        # Stage-2 Re-ranking & Sorting
        sort_mode = request.sort_by or ("distance" if is_near_me else "relevance")

        if sort_mode == "distance" and has_user_coords:
            filtered = sorted(filtered, key=lambda x: (x.get("distance_km") or 999.0, -float(x.get("rating", 0))))
        elif sort_mode == "rating":
            filtered = sorted(filtered, key=lambda x: -float(x.get("rating", 0)))
        elif sort_mode == "price_asc":
            filtered = sorted(filtered, key=lambda x: int(x.get("price_for_two", 9999)))
        else:
            # Blended Two-Stage Relevance Score:
            # Score = Vector_Sim (0.45) + Normalized_Rating (0.25) + Distance_Bonus (0.15) + Tag_Bonus (0.15)
            for c in filtered:
                vec_score = c.get("score", 0.8)
                rating_score = float(c.get("rating", 4.0)) / 5.0
                dist_score = 1.0
                if has_user_coords and c.get("distance_km") is not None:
                    # Decay score beyond 5km
                    dist_score = max(0.0, 1.0 - (c["distance_km"] / 15.0))
                tag_bonus = 0.2 if (vibe and vibe.lower() in " ".join(c.get("tags", [])).lower()) else 0.0
                c["stage2_score"] = (vec_score * 0.45) + (rating_score * 0.25) + (dist_score * 0.15) + tag_bonus

            filtered = sorted(filtered, key=lambda x: -x.get("stage2_score", 0))

        # Top 3-4 final venues
        final_candidates = filtered[:3]

        # Convert to Pydantic Cafe models
        recommended_cafes: List[Cafe] = []
        geo_points: List[GeoPoint] = []

        for c in final_candidates:
            try:
                cafe_model = Cafe(
                    id=c["id"],
                    name=c["name"],
                    area=c["area"],
                    address=c["address"],
                    lat=float(c["lat"]),
                    lng=float(c["lng"]),
                    price_for_two=int(c["price_for_two"]),
                    rating=float(c["rating"]),
                    tags=c["tags"],
                    cuisine=c["cuisine"],
                    dietary=c["dietary"],
                    must_try_dishes=c["must_try_dishes"],
                    highlights=c["highlights"],
                    review_summary=c["review_summary"],
                    google_maps_url=c["google_maps_url"],
                    distance_km=c.get("distance_km"),
                    navigation_url=c.get("navigation_url")
                )
                recommended_cafes.append(cafe_model)
                geo_points.append(GeoPoint(
                    id=cafe_model.id,
                    name=cafe_model.name,
                    lat=cafe_model.lat,
                    lng=cafe_model.lng,
                    area=cafe_model.area,
                    rating=cafe_model.rating,
                    price_for_two=cafe_model.price_for_two,
                    google_maps_url=cafe_model.google_maps_url,
                    tags=cafe_model.tags,
                    distance_km=cafe_model.distance_km,
                    navigation_url=cafe_model.navigation_url
                ))
            except Exception as e:
                logger.error(f"Error parsing candidate into Cafe model: {e}")

        # Step 4: Record user turn in conversational memory
        self.sessions[session_id].append({"role": "user", "text": request.query})

        # Step 5: Synthesis via Gemini or Grounded Reasoner
        answer = ""
        source = "Smart-Grounded-Reasoner"

        if self._gemini_client:
            try:
                from google.genai import types
                prompt = self.format_grounded_prompt(
                    query=request.query,
                    candidate_cafes=final_candidates,
                    has_user_loc=has_user_coords,
                    session_history=self.sessions[session_id]
                )
                cfg = types.GenerateContentConfig(
                    max_output_tokens=350,
                    temperature=0.7,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=types.HttpOptions(timeout=3)
                )
                response = self._gemini_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt,
                    config=cfg
                )
                if response and response.text:
                    answer = response.text
                    source = "Google-Gemini (gemini-3.8-flash)"
            except Exception as e:
                logger.warning(f"Fast Gemini call deferred ({e}). Engaging Smart Grounded Reasoner instantly.")

        if not answer:
            answer = self._synthesize_grounded_fallback(request.query, recommended_cafes, has_user_coords)

        # Record assistant answer in session memory
        self.sessions[session_id].append({"role": "assistant", "text": answer})
        if len(self.sessions[session_id]) > 10:
            self.sessions[session_id] = self.sessions[session_id][-10:]

        user_loc_dict = {"lat": request.user_lat, "lng": request.user_lng} if has_user_coords else None

        return QueryResponse(
            query=request.query,
            answer=answer,
            recommended_cafes=recommended_cafes,
            geo_points=geo_points,
            source=source,
            retrieval_count=len(recommended_cafes),
            user_location=user_loc_dict
        )

    def _synthesize_grounded_fallback(self, query: str, cafes: List[Cafe], has_user_loc: bool = False) -> str:
        """High-fidelity deterministic grounded reasoner when API keys are offline."""
        lines = [
            f"Here are top recommendations tailored to your search (*\"{query}\"*):\n"
        ]

        for i, cafe in enumerate(cafes, 1):
            must_try = ", ".join(cafe.must_try_dishes[:3])
            tags_str = " • ".join(cafe.tags[:3])
            dist_badge = f" | 🚗 **{cafe.distance_km} km away**" if cafe.distance_km is not None else ""
            nav_link = cafe.navigation_url or cafe.google_maps_url

            lines.append(f"### {i}. **{cafe.name}** ({cafe.area})")
            lines.append(f"⭐ **{cafe.rating}/5.0** | 💰 **₹{cafe.price_for_two} for two**{dist_badge} | 🌿 *{cafe.dietary}*")
            lines.append(f"🏷️ *{tags_str}*")
            lines.append(f"\n{cafe.highlights}")
            lines.append(f"\n🍽️ **Must-Try:** {must_try}")
            lines.append(f"📍 **Location:** {cafe.address}")
            lines.append(f"🗺️ [**Start Google Maps Driving Navigation**]({nav_link})\n")

        lines.append("---")
        lines.append("💡 **Local Tip:** Check the live map pins on the right—you can view direct driving routes and live directions from your current position!")

        return "\n".join(lines)
