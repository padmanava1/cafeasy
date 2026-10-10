"""
Cafeasy Vector Store & Hybrid Retrieval Engine
Manages persistent ChromaDB vector storage, embedding generation, and hybrid search
combining dense semantic cosine similarity with structured metadata filtering.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from backend.models import Cafe

logger = logging.getLogger(__name__)


class CafeVectorStore:
    """Manages ChromaDB collections, vector embeddings, and hybrid filtering for Ahmedabad cafes."""

    COLLECTION_NAME = "cafeasy_ahmedabad"

    def __init__(self, persist_dir: Optional[str] = None):
        if not persist_dir:
            base_path = Path(__file__).resolve().parent.parent / "data" / "chroma_db"
            persist_dir = str(base_path)

        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing ChromaDB client with storage at: {persist_dir}")
        self.client = chromadb.PersistentClient(path=self.persist_dir)

        # Default embedding function uses all-MiniLM-L6-v2 ONNX model (fast, 384 dimensions)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"description": "Ahmedabad cafes and dining vector collection"}
        )

    def generate_document_text(self, cafe: Cafe) -> str:
        """
        Creates a dense textual representation of the cafe capturing semantic nuance,
        ambiance, vibes, food specialties, and reviews for embedding.
        """
        return (
            f"{cafe.name} is a cafe in {cafe.area}, Ahmedabad. "
            f"Ambiance and Highlights: {cafe.highlights} "
            f"Tags and Vibe: {', '.join(cafe.tags)}. "
            f"Cuisine: {', '.join(cafe.cuisine)}. "
            f"Dietary: {cafe.dietary}. "
            f"Must-try dishes and drinks: {', '.join(cafe.must_try_dishes)}. "
            f"Cost for two: INR {cafe.price_for_two}. "
            f"Customer reviews: {cafe.review_summary}"
        )

    def ingest_cafes(self, cafes: List[Cafe], force_refresh: bool = False) -> int:
        """Indexes cafe records into the ChromaDB collection with rich metadata payloads."""
        existing_count = self.collection.count()
        if existing_count > 0 and not force_refresh:
            logger.info(f"Collection already has {existing_count} records. Skipping re-ingestion.")
            return existing_count

        if force_refresh and existing_count > 0:
            logger.info(f"Refreshing collection: deleting {existing_count} existing records...")
            self.client.delete_collection(self.COLLECTION_NAME)
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=self.embedding_fn,
                metadata={"description": "Ahmedabad cafes and dining vector collection"}
            )

        ids = []
        documents = []
        metadatas = []

        for cafe in cafes:
            ids.append(cafe.id)
            documents.append(self.generate_document_text(cafe))
            metadatas.append({
                "id": cafe.id,
                "name": cafe.name,
                "area": cafe.area,
                "address": cafe.address,
                "lat": float(cafe.lat),
                "lng": float(cafe.lng),
                "price_for_two": int(cafe.price_for_two),
                "rating": float(cafe.rating),
                "dietary": cafe.dietary,
                "tags": ",".join(cafe.tags),
                "cuisine": ",".join(cafe.cuisine),
                "must_try_dishes": json.dumps(cafe.must_try_dishes),
                "highlights": cafe.highlights,
                "review_summary": cafe.review_summary,
                "google_maps_url": cafe.google_maps_url
            })

        batch_size = 100
        total_batches = (len(ids) + batch_size - 1) // batch_size
        logger.info(f"Ingesting {len(ids)} venues in {total_batches} batches of {batch_size}...")

        for b in range(total_batches):
            start_i = b * batch_size
            end_i = min(start_i + batch_size, len(ids))
            self.collection.add(
                ids=ids[start_i:end_i],
                documents=documents[start_i:end_i],
                metadatas=metadatas[start_i:end_i]
            )
            logger.info(f"Indexed batch {b + 1}/{total_batches} ({end_i}/{len(ids)} venues)")

        total = self.collection.count()
        logger.info(f"Successfully indexed {len(ids)} venues. Total collection size: {total}")
        return total

    def hybrid_search(
        self,
        query: str,
        area: Optional[str] = None,
        max_budget: Optional[int] = None,
        dietary: Optional[str] = None,
        n_results: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Executes a Hybrid Search:
        1. Formulates boolean metadata filters (where clause) for strict scalar constraints.
        2. Computes cosine similarity between query embeddings and candidate document vectors.
        3. Falls back gracefully to relaxed filtering if zero candidates match strict filters.
        """
        filters: List[Dict[str, Any]] = []

        if area:
            filters.append({"area": {"$eq": area}})
        if max_budget:
            filters.append({"price_for_two": {"$lte": max_budget}})
        if dietary and dietary.lower() == "pure veg":
            filters.append({"dietary": {"$eq": "Pure Veg"}})

        where_filter: Optional[Dict[str, Any]] = None
        if len(filters) == 1:
            where_filter = filters[0]
        elif len(filters) > 1:
            where_filter = {"$and": filters}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            # If strict filter returned results, format and return
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                return self._format_results(results)
        except Exception as e:
            logger.warning(f"Filtered query failed or found no candidates: {e}. Falling back to unconstrained semantic search.")

        # Fallback: Query purely on semantic meaning if strict filter is empty
        fallback_results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return self._format_results(fallback_results)

    def _format_results(self, raw_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converts raw ChromaDB query outputs into clean dictionaries."""
        formatted: List[Dict[str, Any]] = []
        if not raw_results or not raw_results.get("ids"):
            return formatted

        ids_list = raw_results["ids"][0]
        metadatas_list = raw_results["metadatas"][0]
        distances = raw_results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids_list):
            meta = metadatas_list[i].copy()
            meta["must_try_dishes"] = json.loads(meta.get("must_try_dishes", "[]"))
            meta["tags"] = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
            meta["cuisine"] = [c.strip() for c in meta.get("cuisine", "").split(",") if c.strip()]
            meta["score"] = float(1.0 - distances[i]) if i < len(distances) else 1.0
            formatted.append(meta)

        return formatted

    def get_all_cafes(self) -> List[Dict[str, Any]]:
        """Retrieves all indexed cafes for catalog listing."""
        results = self.collection.get()
        cafes = []
        if results and results.get("metadatas"):
            for meta in results["metadatas"]:
                clean = meta.copy()
                clean["must_try_dishes"] = json.loads(clean.get("must_try_dishes", "[]"))
                clean["tags"] = [t.strip() for t in clean.get("tags", "").split(",") if t.strip()]
                clean["cuisine"] = [c.strip() for c in clean.get("cuisine", "").split(",") if c.strip()]
                cafes.append(clean)
        return cafes
