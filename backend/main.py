"""
Cafeasy FastAPI Application Server
Provides REST endpoints for conversational AI recommendations, hybrid vector search,
catalog browsing, and serves the static frontend with interactive Leaflet map.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.models import QueryRequest, QueryResponse, Cafe
from rag.vector_store import CafeVectorStore
from rag.rag_engine import CafeasyRAGEngine
from scraper.scraper import AhmedabadCafeScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Cafeasy API",
    description="Location-Aware Hybrid RAG Cafe & Dining Recommendation Engine for Ahmedabad",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core RAG singletons
vector_store: Optional[CafeVectorStore] = None
rag_engine: Optional[CafeasyRAGEngine] = None


@app.on_event("startup")
def startup_event():
    """Initializes vector store, seeds collection if empty, and initializes RAG engine."""
    global vector_store, rag_engine
    logger.info("Initializing Cafeasy vector store and RAG engine...")
    vector_store = CafeVectorStore()

    # Self-heal / auto-seed if collection is fresh or empty
    if vector_store.collection.count() == 0:
        logger.info("Vector collection is empty. Auto-seeding curated Ahmedabad dataset...")
        scraper = AhmedabadCafeScraper()
        cafes = scraper.load_seed_dataset()
        vector_store.ingest_cafes(cafes)

    rag_engine = CafeasyRAGEngine(vector_store=vector_store)
    logger.info(f"Cafeasy ready! Indexed venues: {vector_store.collection.count()}. LLM mode: {'Gemini 1.5' if rag_engine._gemini_client else 'Smart Grounded Reasoner'}")


@app.get("/api/health")
def health_check():
    """Returns system status, vector collection count, and active LLM configuration."""
    if not vector_store or not rag_engine:
        raise HTTPException(status_code=503, detail="System initializing")

    return {
        "status": "healthy",
        "service": "Cafeasy",
        "city": "Ahmedabad",
        "indexed_cafes": vector_store.collection.count(),
        "llm_engine": "Gemini-3.8-Flash" if rag_engine._gemini_client else "Smart-Grounded-Reasoner",
        "has_gemini_key": bool(rag_engine.api_key)
    }


@app.post("/api/chat", response_model=QueryResponse)
def chat_recommendation(request: QueryRequest):
    """
    Primary RAG endpoint:
    Processes user query, applies hybrid search (metadata filter + vector similarity),
    and generates grounded recommendations with verified Google Maps links & GeoJSON.
    """
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not ready")

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    return rag_engine.generate_recommendations(request)


@app.get("/api/cafes", response_model=List[dict])
def list_cafes(
    area: Optional[str] = Query(None, description="Filter by area (e.g. Bodakdev)"),
    max_price: Optional[int] = Query(None, description="Max price for two"),
    tag: Optional[str] = Query(None, description="Filter by tag (e.g. Date Night)")
):
    """Returns catalog of cafes with optional scalar filters."""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    all_cafes = vector_store.get_all_cafes()
    filtered = all_cafes

    if area:
        filtered = [c for c in filtered if c["area"].lower() == area.lower()]
    if max_price:
        filtered = [c for c in filtered if c["price_for_two"] <= max_price]
    if tag:
        filtered = [c for c in filtered if any(tag.lower() in t.lower() for t in c.get("tags", []))]

    return filtered


@app.get("/api/areas")
def list_areas():
    """Returns all available neighborhood areas in Ahmedabad."""
    if not vector_store:
        return []
    cafes = vector_store.get_all_cafes()
    unique_areas = sorted(list(set(c["area"] for c in cafes)))
    return {"areas": unique_areas}


# Serve static frontend files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
