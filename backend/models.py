from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Cafe(BaseModel):
    id: str = Field(..., description="Unique identifier for the cafe")
    name: str = Field(..., description="Name of the restaurant or cafe")
    area: str = Field(..., description="Locality in Ahmedabad (e.g. Bodakdev, Sindhu Bhavan Road)")
    address: str = Field(..., description="Full physical address")
    lat: float = Field(..., description="GPS Latitude coordinate")
    lng: float = Field(..., description="GPS Longitude coordinate")
    price_for_two: int = Field(..., description="Average cost for two people in INR")
    rating: float = Field(..., description="Average rating out of 5.0")
    tags: List[str] = Field(default_factory=list, description="Vibe and feature tags (e.g. Date Night, Work Friendly)")
    cuisine: List[str] = Field(default_factory=list, description="Cuisines served")
    dietary: str = Field("Veg & Non-Veg", description="Dietary classification: Pure Veg or Veg & Non-Veg")
    must_try_dishes: List[str] = Field(default_factory=list, description="Top recommended dishes and drinks")
    highlights: str = Field(..., description="Distinctive features or ambiance description")
    review_summary: str = Field(..., description="Summary of customer reviews")
    google_maps_url: str = Field(..., description="Verified direct Google Maps location URL")
    distance_km: Optional[float] = Field(None, description="Calculated distance in km from user's current location")
    navigation_url: Optional[str] = Field(None, description="Turn-by-turn driving directions URL from user location")


class QueryRequest(BaseModel):
    query: str = Field(..., description="User's natural language search or recommendation query")
    area: Optional[str] = Field(None, description="Optional manual area filter")
    max_budget: Optional[int] = Field(None, description="Optional max price for two")
    vibe: Optional[str] = Field(None, description="Optional vibe preference (e.g. Date Night, Work Friendly)")
    cuisine: Optional[str] = Field(None, description="Optional cuisine preference (e.g. Italian, Coffee, Gujarati)")
    dietary: Optional[str] = Field(None, description="Optional dietary preference (e.g. Pure Veg, Jain)")
    user_lat: Optional[float] = Field(None, description="User's current GPS Latitude")
    user_lng: Optional[float] = Field(None, description="User's current GPS Longitude")
    max_distance_km: Optional[float] = Field(None, description="Optional maximum distance filter in km")
    sort_by: Optional[str] = Field("relevance", description="Sort order: relevance, distance, rating, price_asc")
    session_id: Optional[str] = Field("default", description="Session identifier for multi-turn conversational memory")


class GeoPoint(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    area: str
    rating: float
    price_for_two: int
    google_maps_url: str
    tags: List[str]
    distance_km: Optional[float] = None
    navigation_url: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    recommended_cafes: List[Cafe]
    geo_points: List[GeoPoint]
    source: str
    retrieval_count: int
    user_location: Optional[Dict[str, float]] = None
