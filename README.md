# 🕷️ CrawlRAG — Production Web Scraping & Local RAG Engine

**CrawlRAG** is a fully local, production-grade FastAPI system that crawls websites (including JavaScript / React SPAs), cleans and chunks the text, generates dense embeddings, stores them in a vector database, and answers natural language questions using a local LLM — **no cloud APIs, no OpenAI keys, 100% offline**.

---

## 📚 Comprehensive Documentation Hub (`docs/`)

The [`docs/`](file:///d:/data-scraping-rag/data-scraping/docs/00_master_architecture.md) directory contains complete technical specifications, architectural diagrams, mathematical formulas, and code symbol maps for every component of CrawlRAG:

| Document File | Core Technical Focus & Topics Covered | Key Algorithms & Models | Primary Code Files & Functions |
| :--- | :--- | :--- | :--- |
| 🏛️ [**`00_master_architecture.md`**](file:///d:/data-scraping-rag/data-scraping/docs/00_master_architecture.md) | **Master System Overview**<br>• Executive summary & system flow diagram<br>• The 3 Execution Outcomes (Vector Hit, DB Fallback, Sentinel)<br>• RAG Triad quality evaluation framework | End-to-end 2-tier search & 3-layer anti-hallucination guard flow | System-wide index map |
| 🟢 [**`01_web_scraping_module.md`**](file:///d:/data-scraping-rag/data-scraping/docs/01_web_scraping_module.md) | **Web Scraping Engine**<br>• Playwright Chromium JS hydration for React/Vue SPAs<br>• BFS recursive link crawling & canonical URL deduplication<br>• BeautifulSoup4 structured DOM parsing | Breadth-First Search (BFS)<br>Headless Browser Hydration | [`scraping/service.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/scraping/service.py)<br>[`scraping/fetcher.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/scraping/fetcher.py)<br>[`scraping/parser.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/scraping/parser.py) |
| 🧹 [**`02_cleaning_and_chunking.md`**](file:///d:/data-scraping-rag/data-scraping/docs/02_cleaning_and_chunking.md) | **Cleaning & Chunking**<br>• Boilerplate removal (nav, footers, cookie popups)<br>• Crucial entity preservation (`+91` phones, emails, prices)<br>• Recursive character chunking (400 size / 80 overlap) | Priority Separator Cascade (`\n\n` $\rightarrow$ `\n` $\rightarrow$ `. ` $\rightarrow$ ` `)<br>Orphan Chunk Merging | [`rag/cleaner.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/cleaner.py)<br>[`rag/chunker.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/chunker.py) |
| 📐 [**`03_embeddings_and_vector_store.md`**](file:///d:/data-scraping-rag/data-scraping/docs/03_embeddings_and_vector_store.md) | **Embeddings & Vector Store**<br>• BAAI/bge-small-en-v1.5 (384-dim, MTEB leader, 130MB)<br>• L2 Normalization & Cosine Similarity simplification<br>• NumPy matrix storage ($M \in \mathbb{R}^{N \times 384}$) & BLAS search in **< 1.5ms** | L2 Normalization<br>BLAS Dot-Product Matrix Search | [`rag/embeddings.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/embeddings.py)<br>[`rag/vector_store.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/vector_store.py) |
| 🔍 [**`04_hybrid_search_and_retrieval.md`**](file:///d:/data-scraping-rag/data-scraping/docs/04_hybrid_search_and_retrieval.md) | **Hybrid Search & Retrieval**<br>• Dense + sparse hybrid scoring formula<br>• Semantic Guard Indicator ($\mathbb{I}_{S_{\text{dense}} \ge 0.10}$)<br>• Exact phrase, title, and section header boost weights<br>• Qwen 1.5B query reframing & intent expansion | Dense + Sparse Hybrid Search<br>LLM Query Reframing | [`rag/service.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/service.py#L440)<br>[`rag/llm.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/llm.py) |
| 🤖 [**`05_unified_rag_and_anti_hallucination.md`**](file:///d:/data-scraping-rag/data-scraping/docs/05_unified_rag_and_anti_hallucination.md) | **Unified RAG Engine & Guards**<br>• Single endpoint (`POST /api/v1/rag/answer`) flow<br>• Local Qwen2.5-1.5B-Instruct synthesis (temp=0.1)<br>• 3-layer anti-hallucination network (Pre-LLM coverage, Post-LLM entity grounding `_detect_hallucinated_entities`) | RAG Triad Evaluation Formulas:<br>1. `retrieval_confidence`<br>2. `context_coverage`<br>3. `faithfulness_score` | [`rag/service.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/service.py#L630)<br>[`rag/llm.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/rag/llm.py) |
| 🐘 [**`06_postgresql_database_fallback.md`**](file:///d:/data-scraping-rag/data-scraping/docs/06_postgresql_database_fallback.md) | **PostgreSQL Database Fallback**<br>• Natural Language to SQL (NL-to-SQL) converter<br>• 3 SQL Safety Rules (SELECT-only, keyword block, `LIMIT 20`)<br>• `asyncpg` connection pooling (min=1, max=5, 30s timeout)<br>• `cars` table schema & ILIKE keyword fallback search | NL-to-SQL Conversion<br>`asyncpg` Connection Pooling | [`database/nl_to_sql.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/database/nl_to_sql.py)<br>[`database/repository.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/database/repository.py)<br>[`database/connection.py`](file:///d:/data-scraping-rag/data-scraping/backend/app/modules/database/connection.py) |

---

## 📋 Table of Contents

1. [Architecture & End-to-End Flow](#architecture--end-to-end-flow)
2. [Models Used](#models-used)
3. [Libraries Used](#libraries-used)
4. [Project Structure](#project-structure)
5. [Setup & Installation](#setup--installation)
6. [Configuration (.env)](#configuration-env)
7. [All API Endpoints](#all-api-endpoints)
8. [Typical Usage Workflow](#typical-usage-workflow)
9. [Run Tests](#run-tests)

---

## 🏗️ Architecture & End-to-End Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                        STAGE 1 — WEB SCRAPING                        │
│                                                                      │
│  Seed URL  ──►  Playwright (JS rendering) / HTTPX (static)          │
│                ──►  BeautifulSoup HTML Parser                        │
│                     ├── Extracts: title, headings (h1–h6),           │
│                     │   paragraphs, internal/external links          │
│                     └── Saves each page as JSON  →  data/scraped/    │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      STAGE 2 — TEXT CLEANING                         │
│                                                                      │
│  data/scraped/*.json  ──►  TextCleaner                               │
│    ├── Strips: cookie banners, nav noise, footer boilerplate         │
│    ├── Preserves: headings, contact info, phone, email, prices       │
│    └── Output  →  data/clean_data/                                   │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     STAGE 3 — RECURSIVE CHUNKING                     │
│                                                                      │
│  data/clean_data/*.json  ──►  RecursiveCharacterChunker              │
│    ├── Splits by: \n\n → \n → ". " → " " → character                │
│    ├── chunk_size = 400 chars, chunk_overlap = 80 chars              │
│    ├── Merges orphan short chunks (<60 chars) into neighbours        │
│    └── Output  →  data/chunked_data/                                 │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    STAGE 4 — DENSE EMBEDDINGS                        │
│                                                                      │
│  Chunk texts  ──►  BAAI/bge-small-en-v1.5                            │
│    ├── 384-dimensional L2-normalised float32 vectors                 │
│    ├── Cached locally in  models/embeddings/                         │
│    └── Output  →  data/vector_store/vector_index.npy                │
│                    data/vector_store/metadata.json                   │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   STAGE 5 — HYBRID RETRIEVAL                         │
│                                                                      │
│  User query  ──►  Embed query (BAAI/bge-small-en-v1.5)              │
│               ──►  Cosine similarity (numpy dot product)             │
│               ──►  + Keyword/phrase boost on chunk text & title      │
│               ──►  Optional: LLM query reframing (Qwen2.5-1.5B)     │
│               ──►  Top-K ranked results                              │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  STAGE 6 — GROUNDED ANSWER GENERATION                │
│                                                                      │
│  Retrieved chunks  ──►  Qwen/Qwen2.5-1.5B-Instruct (local LLM)      │
│    ├── System prompt enforces: factual, no hallucination, no         │
│    │   meta-commentary ("Based on the context…")                     │
│    ├── max_new_tokens = 512, temperature = 0.1                       │
│    ├── LLMOutputCleaner post-processes: strips robotic phrases,      │
│    │   code artifacts, escaped chars                                 │
│    └── Returns: { query, answer, sources[] }                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Models Used

| Component | Model | Size | Purpose | Cached At |
|---|---|---|---|---|
| **Embeddings** | `BAAI/bge-small-en-v1.5` | ~130 MB | Top-tier 384-dim dense vector embeddings for semantic similarity | `models/embeddings/` |
| **LLM** | `Qwen/Qwen2.5-1.5B-Instruct` | ~3 GB | Instruction-tuned causal LLM for high-accuracy grounded answer generation and query reframing | `models/llm/` |

### Why these models?
- **BAAI/bge-small-en-v1.5**: One of the highest scoring small embedding models on the Massive Text Embedding Benchmark (MTEB). Produces 384-dim normalized vectors that drastically improve context retrieval over standard MiniLM models.
- **Qwen2.5-1.5B-Instruct**: A massive jump in reasoning, instruction-following, and multi-fact extraction capability compared to 0.5B models, while still lightweight enough to run smoothly on local CPU/GPU without cloud dependencies.

---

## 📦 Libraries Used

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | ≥0.111 | REST API framework with automatic OpenAPI/Swagger docs |
| `uvicorn[standard]` | ≥0.30 | ASGI server to run FastAPI |
| `pydantic` | ≥2.7 | Request/response validation and settings management |
| `pydantic-settings` | ≥2.2 | `.env` file loading into Settings class |
| `httpx` | ≥0.27 | Async HTTP client for static page scraping |
| `playwright` | ≥1.44 | Headless Chromium for JavaScript / React SPA rendering |
| `beautifulsoup4` | ≥4.12 | HTML parsing, heading extraction, link discovery |
| `lxml` | ≥5.2 | Fast HTML parser backend for BeautifulSoup |
| `tenacity` | ≥8.3 | Retry logic with exponential back-off for network calls |
| `aiofiles` | ≥23.2 | Async file I/O for reading/writing JSON without blocking |
| `sentence-transformers` | ≥3.0 | Loads and runs `all-MiniLM-L6-v2` embedding model |
| `transformers` | ≥4.41 | Loads and runs `Qwen2.5-0.5B-Instruct` LLM |
| `torch` | ≥2.2 | PyTorch backend for model inference (CPU or CUDA) |
| `numpy` | ≥1.26 | Fast vector math for cosine similarity search |
| `huggingface_hub` | ≥0.23 | Model downloading from Hugging Face Hub |

---

## 📁 Project Structure

```
data-scraping/
├── backend/                           # 🐍 Python FastAPI Backend & AI Pipeline
│   ├── app/
│   │   ├── main.py                    # FastAPI app, routers, CORS, lifespan
│   │   ├── core/
│   │   │   ├── config.py              # Application settings (loaded from .env)
│   │   │   └── logging.py             # Rotating file logger + module loggers
│   │   └── modules/
│   │       ├── scraping/              # Spider crawler, parsers, json store
│   │       └── rag/                   # Cleaner, chunker, BGE embeddings, Qwen LLM
│   ├── data/
│   │   ├── scraped/                   # Raw scraped JSON files (one per page)
│   │   ├── clean_data/                # Cleaned JSON files
│   │   ├── chunked_data/              # Semantic chunked JSON files
│   │   └── vector_store/              # vector_index.npy + metadata.json
│   ├── models/
│   │   ├── embeddings/                # Local cache for BAAI/bge-small-en-v1.5
│   │   └── llm/                       # Local cache for Qwen2.5-1.5B-Instruct
│   ├── logs/
│   │   └── crawlrag.log               # Rotating server audit logs
│   ├── scripts/
│   │   └── download_models.py         # Offline model pre-downloader
│   ├── tests/                         # Automated unit & integration tests
│   ├── .env                           # Local environment configuration
│   ├── .env.example                   # Template for .env
│   ├── requirements.txt               # Backend Python dependencies
│   ├── CrawlRAG.postman_collection.json # Complete Postman API collection
│   └── README.md                      # Backend specific documentation
│
├── frontend/                          # 🎨 Modern React + Vite AI Dashboard
│   ├── src/
│   │   ├── components/                # Header, Sidebar, ChatArea, SourceCard, Stepper
│   │   ├── api/client.js              # FastAPI connector client
│   │   ├── index.css                  # Obsidian Glassmorphism design system
│   │   └── App.jsx                    # Root state & workflow coordinator
│   ├── package.json                   # Frontend dependencies
│   ├── vite.config.js                 # Dev server & reverse proxy to backend
│   └── README.md                      # Frontend specific documentation
│
└── README.md                          # Root project documentation
```

---

## ⚙️ Setup & Installation

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**
- **pip** (latest)
- **Git**

---

### 1️⃣ Start the Backend (FastAPI + AI RAG)

In your first terminal:

```powershell
# Navigate into backend directory
cd backend

# Create & activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install Python requirements & Playwright browser
pip install -r requirements.txt
playwright install chromium

# Start the FastAPI Server
uvicorn app.main:app --reload --port 8000
```

* **Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Backend Health:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

### 2️⃣ Start the Frontend (React AI Dashboard)

In a second terminal:

```powershell
# Navigate into frontend directory
cd frontend

# Install npm dependencies (first time only)
npm install

# Start the Vite dev server
npm run dev
```

* **Web UI Dashboard:** 👉 **[http://localhost:5173](http://localhost:5173)**

The defaults in `.env` work out of the box. Key values:

```env
DEFAULT_CHUNK_SIZE=400        # Characters per chunk
DEFAULT_CHUNK_OVERLAP=80      # Overlap between chunks
LLM_MAX_NEW_TOKENS=512        # Max tokens the LLM generates
LLM_TEMPERATURE=0.1           # Low = factual; 0.0 = greedy/deterministic
RETRIEVAL_TOP_K=7             # How many chunks to retrieve per query
RETRIEVAL_SCORE_THRESHOLD=0.2 # Minimum similarity score (0–1)
```

### Step 5 — Start the Server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI |
| `http://127.0.0.1:8000/redoc` | ReDoc documentation |
| `http://127.0.0.1:8000/health` | Health check (shows log file path) |
| `http://127.0.0.1:8000/` | API overview & key endpoint links |

### Step 6 — (Optional) Pre-download Models

Models are downloaded automatically on first use. To download them manually upfront:

```powershell
python scripts/download_models.py
```

---

## 🔧 Configuration (.env)

```env
# ── Application ────────────────────────────────────────
APP_NAME=CrawlRAG
APP_ENV=development
DEBUG=True
HOST=0.0.0.0
PORT=8000
API_V1_PREFIX=/api/v1

# ── Storage Paths (relative to project root) ───────────
SCRAPED_DIR=data/scraped
CLEAN_DATA_DIR=data/clean_data
CHUNKED_DATA_DIR=data/chunked_data
VECTOR_STORE_DIR=data/vector_store
EMBEDDINGS_DIR=models/embeddings
LLM_DIR=models/llm
LOG_DIR=logs

# ── Scraping ───────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS=30.0
DEFAULT_MAX_DEPTH=2
DEFAULT_MAX_PAGES=50

# ── Embedding Model ────────────────────────────────────
DEFAULT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# ── Chunking (tuned for retrieval accuracy) ────────────
DEFAULT_CHUNK_SIZE=400
DEFAULT_CHUNK_OVERLAP=80

# ── LLM Generation ────────────────────────────────────
DEFAULT_LLM_MODEL=Qwen/Qwen2.5-0.5B-Instruct
LLM_MAX_NEW_TOKENS=512
LLM_TEMPERATURE=0.1

# ── RAG Retrieval ──────────────────────────────────────
RETRIEVAL_TOP_K=7
RETRIEVAL_SCORE_THRESHOLD=0.2
```

---

## 🌐 All API Endpoints

Base URL: `http://127.0.0.1:8000`

---

### 🔵 Health & Info

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API overview, module status, key endpoint links |
| `GET` | `/health` | Server health, log file path, directory paths |

---

### 🟠 Web Scraping — `/api/v1/scraping/`

#### `POST /api/v1/scraping/scrape`
Crawl a website from a seed URL. Renders JavaScript with Playwright, discovers all internal links via BFS, saves each page as a JSON file in `data/scraped/`.

**Request Body:**
```json
{
  "url": "https://books.toscrape.com/",
  "max_depth": 2,
  "max_pages": 50,
  "render_js": true,
  "wait_seconds": 2.0,
  "concurrency": 3,
  "delay_seconds": 0.5,
  "stay_within_path": false,
  "crawl_external_links": false,
  "force_refresh": false
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | string | **required** | Seed URL to start crawling from |
| `max_depth` | int | `2` | BFS depth limit (0 = seed page only) |
| `max_pages` | int | `50` | Maximum total pages to scrape |
| `render_js` | bool | `true` | Use Playwright for JS/React SPAs |
| `wait_seconds` | float | `2.0` | Wait time for JS hydration |
| `concurrency` | int | `3` | Parallel page requests |
| `delay_seconds` | float | `0.5` | Polite delay between requests |
| `stay_within_path` | bool | `false` | Only crawl URLs under seed path |
| `crawl_external_links` | bool | `true` | Also crawl external URLs found on pages |
| `force_refresh` | bool | `false` | Re-scrape even if cached JSON exists |

---

#### `GET /api/v1/scraping/documents`
List all stored scraped JSON documents with pagination and optional search filter.

**Query Params:** `?skip=0&limit=50&query=books`

---

#### `GET /api/v1/scraping/documents/{doc_id}`
Retrieve the full structured JSON of a specific scraped document.

---

#### `DELETE /api/v1/scraping/documents/{doc_id}`
Delete a scraped document JSON file from disk.

---

### 🟢 RAG Pipeline — `/api/v1/rag/`

> **Recommended order for first-time setup:** `embed-all` → `search` or `answer`
> The `embed-all` endpoint runs the full pipeline automatically (clean → chunk → embed).

---

#### `POST /api/v1/rag/clean`
Clean a specific (or all) raw scraped JSON files. Removes boilerplate, normalises whitespace, preserves headings and contact info. Saves to `data/clean_data/`.

```json
{
  "doc_id": null,
  "remove_boilerplate": true,
  "min_paragraph_length": 20
}
```
Set `doc_id` to a specific ID to clean one document, or `null` to clean all.

---

#### `POST /api/v1/rag/clean-all`
Batch clean all scraped documents at once.
```json
{ "remove_boilerplate": true, "min_paragraph_length": 20 }
```

---

#### `POST /api/v1/rag/chunk`
Split cleaned documents into overlapping semantic chunks. Saves to `data/chunked_data/`.
```json
{
  "doc_id": null,
  "chunk_size": 400,
  "chunk_overlap": 80
}
```

---

#### `POST /api/v1/rag/chunk-all`
Clean and chunk ALL scraped documents in one combined operation (no body required).

---

#### `POST /api/v1/rag/embed`
Generate embeddings for a specific (or all) chunked document(s) and insert into the vector store.
```json
{ "doc_id": null, "batch_size": 32 }
```

---

#### `POST /api/v1/rag/embed-all` ⭐ Recommended
**Full pipeline in one call**: clean all → chunk all → embed all → store in vector DB.
Clears and rebuilds the vector index from scratch for a clean, deduplicated result.
```json
{ "batch_size": 32 }
```

---

#### `POST /api/v1/rag/search`
Semantic similarity search over indexed chunks. Returns ranked chunks with scores.
```json
{
  "query": "what books are available in mystery category",
  "top_k": 7,
  "score_threshold": 0.2,
  "reframe": false,
  "temperature": 0.1
}
```
> Tip: Set `reframe: true` to let the LLM rewrite the query for better recall on vague or short queries.

**Response:**
```json
[
  {
    "chunk_id": "doc_abc123_chunk_005",
    "doc_id": "doc_abc123",
    "url": "https://books.toscrape.com/mystery",
    "title": "Mystery Books",
    "text": "...",
    "score": 0.8421,
    "chunk_index": 5
  }
]
```

---

#### `POST /api/v1/rag/answer` ⭐ Key Endpoint
Retrieve relevant context chunks and generate a grounded natural-language answer using the local Qwen2.5-0.5B-Instruct LLM.
```json
{
  "query": "Tell me about Lab Girl book",
  "top_k": 7,
  "score_threshold": 0.2,
  "reframe": true,
  "temperature": 0.1,
  "max_new_tokens": 512
}
```

**Response:**
```json
{
  "query": "Tell me about Lab Girl book",
  "answer": "Lab Girl is a memoir by Hope Jahren priced at £45.17. It is in stock and categorised under Autobiography.",
  "sources": [ { "chunk_id": "...", "title": "...", "text": "...", "score": 0.91 } ],
  "sources_count": 3
}
```

> Also accepts `question`, `prompt`, `q`, `input`, or `text` as aliases for `query`.

---

#### `GET /api/v1/rag/status`
Get pipeline health metrics: file counts at each stage, vector store size, model cache status.

**Response:**
```json
{
  "scraped_document_count": 45,
  "cleaned_document_count": 45,
  "chunked_document_count": 45,
  "vector_count": 1240,
  "embedding_dimension": 384,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "embedding_model_cached_locally": true,
  "llm_model": "Qwen/Qwen2.5-0.5B-Instruct",
  "llm_model_cached_locally": true,
  "vector_store_stats": { "disk_size_bytes": 1920000, ... }
}
```

---

## 🔄 Typical Usage Workflow

```
Step 1: Scrape your website
  POST /api/v1/scraping/scrape
  { "url": "https://yoursite.com", "max_depth": 2, "max_pages": 50 }

Step 2: Build the RAG index (full pipeline in one call)
  POST /api/v1/rag/embed-all
  { "batch_size": 32 }
  ↳ Automatically: clean → chunk → embed → store

Step 3: Check pipeline status
  GET /api/v1/rag/status

Step 4: Ask questions
  POST /api/v1/rag/answer
  { "query": "What services do you offer?", "reframe": true }

Step 5 (optional): Just retrieve chunks without LLM
  POST /api/v1/rag/search
  { "query": "contact address phone number", "top_k": 5 }
```

---

## 📮 Postman Collection

Import [`CrawlRAG.postman_collection.json`](./CrawlRAG.postman_collection.json) into Postman.

The collection includes:
- Pre-configured `base_url` variable (`http://127.0.0.1:8000`)
- `doc_id` variable for document operations
- All endpoints organised in execution order
- Example request bodies for every endpoint

---

## 🧪 Run Automated Tests

```powershell
python -m unittest discover tests
```

---

## 📝 Logs

Application logs are written to `logs/crawlrag.log` with automatic rotation (10 MB per file, 5 backups kept).

Each log line format:
```
2026-08-16 12:00:00 | INFO     | [crawlrag.app.modules.rag.service] message
```

To follow logs in real time:
```powershell
Get-Content logs\crawlrag.log -Wait -Tail 50
```

---

## 🗂️ Data Flow Summary

```
Website URL
  │
  ├─ POST /scraping/scrape          → data/scraped/*.json
  │
  ├─ POST /rag/clean (or embed-all) → data/clean_data/*.json
  │
  ├─ POST /rag/chunk (or embed-all) → data/chunked_data/*_chunks.json
  │
  ├─ POST /rag/embed (or embed-all) → data/vector_store/vector_index.npy
  │                                   data/vector_store/metadata.json
  │
  ├─ POST /rag/search               → top-K ranked chunk results
  │
  └─ POST /rag/answer               → grounded LLM answer + sources
```
