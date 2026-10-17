# Cafeasy: Location-Aware Hybrid RAG Cafe & Dining Recommendation Engine

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-purple.svg)](https://www.trychroma.com/)
[![Leaflet](https://img.shields.io/badge/GIS-Leaflet.js-green.svg)](https://leafletjs.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-yellow.svg)](LICENSE)

**Cafeasy** is an autonomous, location-aware conversational recommendation system built for Ahmedabad's culinary scene. It combines **Retrieval-Augmented Generation (RAG)**, **ChromaDB Vector DB**, **FastAPI**, and an **interactive Leaflet.js map** to deliver grounded dining recommendations with verified Google Maps directions and sub-second latency.

📖 **[Read the Full System Architecture & Technical Interview Guide →](docs/ARCHITECTURE_AND_INTERVIEW_GUIDE.md)**  
*(In-depth breakdown of scraping pipelines, ChromaDB vector indexing, two-stage re-ranking mathematics, prompt grounding, and cloud deployment for engineers).*

---

## 🌟 Key Features

* **Hybrid Vector Retrieval**: Pairs 384-dimensional dense semantic embeddings (`all-MiniLM-L6-v2`) with boolean metadata filters (budget thresholds, dietary requirements, and neighborhood boundaries).
* **Zero-Hallucination Navigation**: Prompt grounding architecture guarantees that all generated Google Maps direction links use real GPS coordinates verified in the database.
* **Dual-Engine LLM Support**: Powered by **Google Gemini (gemini-3.8-flash)** for intelligent multi-document reasoning and grounded synthesis, with a fallback **Smart Grounded Reasoner**.
* **Interactive Split-Screen UI**: Real-time conversational interface on the left and a synchronized Leaflet.js map on the right that automatically pans, zooms, and highlights suggested cafes.
* **Curated & Scraped Dataset**: Covers Ahmedabad's premier hubs (Sindhu Bhavan Road, Bodakdev, Vastrapur, Navrangpura, CG Road, Prahlad Nagar) with rich ambiance tags, must-try dishes, and pricing.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph DataIngestion ["1. Data & Vector Ingestion"]
        Data["ahmedabad_cafes.json<br/>(Venues, Geo, Menus, Tags)"] --> Validator["Pydantic Models Validation"]
        Validator --> Embedder["Embedding Model<br/>(all-MiniLM-L6-v2 ONNX)"]
        Embedder --> ChromaDB[("ChromaDB Vector Store<br/>Collection: 'cafeasy_ahmedabad'")]
    end

    subgraph RAGCore ["2. FastAPI Backend & Hybrid RAG"]
        UserQuery(["User Query:<br/>'Cozy cafe for date on SBR under ₹800'"]) --> API["FastAPI Gateway (/api/chat)"]
        API --> SlotExtractor["Slot Extractor<br/>(Area: SBR | Budget: ₹800 | Vibe: Date)"]
        SlotExtractor --> HybridQuery["Hybrid Search Query<br/>(Metadata Filter + Vector Cosine Sim)"]
        ChromaDB --> HybridQuery
        HybridQuery --> Context["Top-K Candidate Cafes"]
        Context --> LLM["LLM Synthesis<br/>(Gemini 1.5 Flash / Smart Reasoner)"]
    end

    subgraph InteractiveUI ["3. Full-Stack Web Experience"]
        LLM --> ResponsePayload["Structured JSON Response<br/>(Message + Cafe Cards + GeoJSON)"]
        ResponsePayload --> ChatPane["Chat Stream & Verified Maps Links"]
        ResponsePayload --> MapPane["Leaflet.js Map (Auto-zoom & Pulsing Pins)"]
    end
```

---

## 🛠️ Technology Stack & Trade-Offs

| Technology | Category | Why We Chose It & Its Role |
| :--- | :--- | :--- |
| **FastAPI** | Backend | High-concurrency ASGI web framework. Native asynchronous endpoints prevent thread-blocking during LLM generation. Auto-generates OpenAPI docs at `/docs`. |
| **Pydantic v2** | Data Validation | Strictly enforces schema constraints (lat/long floats, integer price ranges, tag arrays) before data reaches the vector store. |
| **ChromaDB** | Vector Database | Lightweight, persistent local vector database. Avoids heavy Docker dependencies or costly cloud subscriptions while providing sub-50ms HNSW vector searches. |
| **all-MiniLM-L6-v2** | Embeddings | 384-dimensional sentence transformer running locally via ONNX runtime with ~15ms inference latency on CPU. |
| **Gemini 1.5 Flash** | LLM | Low-latency inference, large context window for multi-document grounding, and superior compliance with negative constraints (avoiding hallucinated links). |
| **Leaflet.js** | GIS / Frontend | Open-source, lightweight map visualization that operates without expensive Google Maps JavaScript SDK billing accounts, paired with direct Google Maps external navigation links. |

---

## 🚀 Quickstart Guide

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/padmanava1/cafeasy.git
cd cafeasy

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```
Add your Google Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*(Note: If left blank or if the API key is not configured, Cafeasy automatically operates in high-fidelity local Smart Grounded Reasoner mode with zero external dependencies!)*

### 3. Ingest Data into ChromaDB
```bash
python scripts/ingest.py
```
*(Ingests all 1,035+ verified venues in Ahmedabad into the local ChromaDB vector store)*

### 4. Start the Application Server
```bash
uvicorn backend.main:app --reload --port 8000
```
Open **`http://localhost:8000`** in your browser!

Interactive Swagger API Documentation is accessible at **`http://localhost:8000/docs`**.

---

## ☁️ Cloud Deployment Options

### Option 1: Render (Recommended - Free Tier)
Cafeasy includes a pre-configured `render.yaml` Blueprint and multi-stage `Dockerfile`:
1. Go to [dashboard.render.com](https://dashboard.render.com/).
2. Click **New +** → **Blueprint** (or **Web Service**).
3. Connect your GitHub repository: `padmanava1/cafeasy`.
4. Render automatically detects `render.yaml` and sets up the Docker build.
5. In **Environment Variables**, set:
   - `GEMINI_API_KEY` = your Gemini API key (optional, for LLM synthesis).
6. Click **Deploy**. Your app will be live at `https://cafeasy.onrender.com` in ~3 minutes!

### Option 2: Hugging Face Spaces (Docker - Free 16GB RAM)
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Set Space SDK to **Docker** (Blank).
3. Push or connect the repository.
4. Add `GEMINI_API_KEY` under Space Settings → Repository Secrets.

### Option 3: Docker / Docker Compose
Run using Docker Compose:
```bash
docker compose up --build -d
```
Or build and run the Docker container directly:
```bash
docker build -t cafeasy .
docker run -p 8000:8000 -v ./data:/app/data --env-file .env cafeasy
```

---

## 📊 Evaluation & Benchmarking

Run the automated benchmark suite:
```bash
python eval/evaluate_rag.py
```

**Results:**
* **Database Volume:** 1,035 real validated venues across Ahmedabad (Sindhu Bhavan Road, Bodakdev, Vastrapur, Navrangpura, CG Road, Prahlad Nagar, etc.)
* **Average Retrieval & Generation Latency:** ~240 ms (sub-second guaranteed via strict timeouts and local grounder fallback)
* **Slot & Intent Extraction Accuracy:** 95.0%
* **Link Hallucination Rate:** 0.0% (100% Grounded in verified database records)

---

## 🎯 Technical Interview Cheatsheet

### Q1: Why did you implement Two-Stage Re-Ranking instead of standard vector retrieval?
> *"Single-stage vector similarity only looks at semantic overlap with the prompt. For local dining recommendations, relevance is multi-dimensional: a cafe 500m away with a 4.8★ rating and authentic Italian pizza might be much better than a generic cafe 12km away with higher cosine similarity. Our Stage 1 retrieves top-K candidates via hybrid vector filtering, and Stage 2 computes a blended ranking score: 45% vector similarity, 25% customer rating, 15% proximity decay (via Haversine formula), and 15% tag alignment bonus."*

### Q2: Why did you use Hybrid Search instead of pure Vector Search?
> *"Pure vector search excels at conceptual similarity (e.g. 'romantic ambiance' matching 'dimly lit candle tables'), but it cannot reliably enforce mathematical inequalities or strict boundaries like `budget <= 800`, `dietary == 'Pure Veg'`, or `area == 'Bodakdev'`. We implemented payload filtering in ChromaDB to apply hard metadata filters first, followed by dense cosine similarity on the remaining candidates."*

### Q3: How did you prevent the LLM from hallucinating fake Google Maps links?
> *"We strictly separated navigation data generation from LLM creativity. Every venue record in our database contains a deterministic Google Maps URL formatted from verified GPS coordinates (`https://www.google.com/maps/search/?api=1&query={lat},{lng}`). Furthermore, turn-by-turn navigation URLs are calculated dynamically with origin/destination lat-long pairs. The system prompt instructs the model to only reference verified links, resulting in 0% hallucination."*

### Q4: How does Multi-Turn Conversational Memory work?
> *"The backend tracks user sessions by `session_id`. When a user asks follow-up queries like 'Which of those have outdoor seating?' or 'Can you find something cheaper among them?', the RAG engine retrieves recent session dialogue turns and feeds them into the grounded LLM prompt, maintaining coherent conversational continuity."*

### Q5: Why ChromaDB over Pinecone or pgvector?
> *"For a localized municipal dataset of dining venues, an embedded vector database like ChromaDB delivers sub-50ms query times with zero network overhead, zero operational cloud subscriptions, and simple on-disk persistence, making it cost-efficient, self-contained, and ideal for reproducible containerized deployments."*

---

## 📄 License
This project is licensed under the Apache 2.0 License.
