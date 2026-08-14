# 🕷️ CrawlRAG - Production Web Scraping & AI RAG Ingestion Engine

**CrawlRAG** is a production-grade, modular FastAPI system designed to crawl websites, render dynamic JavaScript / React SPAs, extract clean data, execute hierarchical text chunking, generate local vector embeddings, and power semantic RAG search with local LLM integration.

---

## 🏗️ End-to-End Architecture & Flow

```text
[ Website / SPA ] 
       │
       ▼  (Playwright / HTTPX Crawler)
[ Raw JSON (`data/scraped/`) ]
       │
       ▼  (Text Cleaning Pipeline: removes boilerplate, preserves contact/phone data)
[ Processed Text (`data/processed/`) ]
       │
       ▼  (Recursive Character Chunker: 250 chars chunk size, 50 overlap)
[ Semantic Chunks ]
       │
       ▼  (sentence-transformers/all-MiniLM-L6-v2 - Free Local Model)
[ Dense Vector Embeddings (384-dim) ]
       │
       ▼  (Numpy Cosine Similarity Vector Store + Hybrid Keyword Intent Boosting)
[ Semantic Search API (`/api/v1/rag/search`) ]
```

---

## 🤖 Models Used & Why

| Component | Model Name | Role & Reason |
| :--- | :--- | :--- |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | **Free, lightweight, highly accurate** 384-dimensional embedding model optimized for semantic sentence similarity and local offline caching (`models/embeddings/`). |
| **LLM & Reframing** | `Qwen/Qwen2.5-0.5B-Instruct` | **Free, compact instruction-tuned causal LLM** used for query optimization, reframing, and temperature-controlled generation (`models/llm/`). |

---

## 🔍 Key Retrieval & Chunking Strategies

1. **Text Cleaning Pipeline**:
   - Strips cookie banners, tracking scripts, and excessive whitespace.
   - Preserves critical contact entities (phone numbers like `+91 ...`, email addresses, and address lines) to prevent data loss.

2. **Recursive Character Chunking**:
   - Hierarchically splits text using natural separators (`\n\n`, `\n`, `. `, ` `, ``) with a configured chunk size of `250` characters and `50` character overlap.
   - **Why?** Prevents sentences/paragraphs from being cut arbitrarily in half, maintaining semantic context and continuity across chunks.

3. **Hybrid Semantic + Keyword-Boosted Search**:
   - Combines **Dense Vector Cosine Similarity** (`all-MiniLM-L6-v2`) with **Intent-Based Keyword Boosting** (prioritizing contact details, phone numbers, and addresses when queries contain phone/address/contact keywords).

---

## 🌐 Complete API Endpoints

### 1. Web Scraping (`/api/v1/scraping/`)
* **`POST /api/v1/scraping/scrape`**: Unified spider crawler (Playwright + BeautifulSoup + JSON persistence).
* **`GET /api/v1/scraping/documents`**: List stored JSON documents with pagination.
* **`GET /api/v1/scraping/documents/{doc_id}`**: Get full document JSON.
* **`DELETE /api/v1/scraping/documents/{doc_id}`**: Delete document from disk.

### 2. RAG Pipeline & Vector DB (`/api/v1/rag/`)
* **`POST /api/v1/rag/clean`**: Clean raw scraped JSON docs into `data/processed/`.
* **`POST /api/v1/rag/chunk`**: Run recursive character chunking.
* **`POST /api/v1/rag/embed`**: Download model (if needed), generate embeddings, and index into vector store.
* **`POST /api/v1/rag/search`**: Semantic vector similarity search with hybrid keyword boosting & temperature control.
* **`GET /api/v1/rag/status`**: Pipeline & vector store health metrics.

---

## ⚡ Quickstart & Setup

### 1. Install Dependencies
```powershell
# Activate venv
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Start the FastAPI Server
```powershell
python -m uvicorn app.main:app --reload --port 8000
```
* **Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 📮 Postman Collection
Import [`CrawlRAG.postman_collection.json`](file:///d:/data-scraping/CrawlRAG.postman_collection.json) into Postman to test all scraping and RAG endpoints.

---

## 🧪 Run Automated Tests
```powershell
python -m unittest discover tests
```
