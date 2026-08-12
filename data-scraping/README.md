# 🕷️ CrawlRAG - Production Web Scraping & AI RAG Ingestion Engine

**CrawlRAG** is a production-grade, modular FastAPI system designed to crawl websites, render dynamic JavaScript / React SPAs, extract 100% of clean text and hierarchical Markdown, and persist structured JSON data ready for Vector Embeddings and RAG Chatbot pipelines.

---

## 📁 Project Structure

```text
data-scraping/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI entry point & lifespan manager
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic Settings (.env loader & storage paths)
│   │   └── logging.py                 # Structured logger
│   └── modules/
│       ├── __init__.py
│       └── scraping/                  # MODULE 1: Web Scraping & Crawler Engine
│           ├── __init__.py
│           ├── schemas.py             # Pydantic schemas (Unified request/response, documents)
│           ├── parsers.py             # BeautifulSoup parser (100% text, headings, clean markdown)
│           ├── crawler.py             # Thread-safe Playwright + HTTPX Async Spider Crawler
│           ├── json_store.py          # JSON File Storage Manager & SHA-256 Hasher
│           ├── service.py             # Scraping orchestrator
│           └── router.py              # REST API router (/scrape, /documents)
│
├── scripts/
│   └── download_models.py             # Hugging Face model downloader for embeddings & LLMs
│
├── data/
│   └── scraped/                       # JSON document storage location
│
├── models/                            # Local directory for cached Hugging Face models
│   ├── embeddings/                    # Vector embedding models (e.g. BAAI/bge-small-en-v1.5)
│   └── llm/                           # LLM weights and tokenizers (e.g. Qwen2.5-0.5B-Instruct)
│
├── tests/
│   └── test_scraping_module.py        # Automated test suite
│
├── CrawlRAG.postman_collection.json   # Ready-to-import Postman Collection
├── requirements.txt                   # Production Python dependencies
├── .env.example                       # Configuration template
├── .env                               # Active environment variables
└── README.md
```

---

## ⚡ Quickstart & Setup

### 1. Install Dependencies
Activate your virtual environment and install dependencies:

```powershell
# Activate your venv
.\venv\Scripts\activate
# (or if located in parent: ..\venv\Scripts\activate)

# Install requirements
pip install -r requirements.txt

# Install Playwright Chromium headless browser
playwright install chromium
```

### 2. Start the FastAPI Server

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

* 📖 **Interactive Swagger UI (API Docs):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* 📑 **ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* 🩺 **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🌐 API Endpoints

### 1. Unified Scraping & Spider Crawler
**`POST /api/v1/scraping/scrape`**

**One single endpoint for everything**:
1. Takes **1 Seed URL** (e.g. `https://humanixtechnologies.com/`).
2. Renders dynamic client-side JavaScript / React / Vue SPAs with automated progressive scrolling.
3. Extracts **100% of all text, structured headings (`h1`-`h6`), clean markdown, and contact info**.
4. Automatically discovers all internal links on that page.
5. Recursively visits and scrapes each subpage one-by-one up to `max_depth` and `max_pages`.
6. Saves each page into its own individual JSON file in `data/scraped/{doc_id}.json`.
7. Directly returns the **full structured JSON data of all scraped pages** in the response body.

**Request Body:**
```json
{
  "url": "https://humanixtechnologies.com/",
  "max_depth": 2,
  "max_pages": 15,
  "render_js": true,
  "wait_seconds": 2.5,
  "concurrency": 2,
  "delay_seconds": 0.5,
  "stay_within_path": false,
  "force_refresh": true
}
```

*Note: For scraping only a single page without following links, set `"max_depth": 0` or `"max_pages": 1`.*

---

### 2. List Stored JSON Documents
**`GET /api/v1/scraping/documents?skip=0&limit=50`**

Returns lightweight metadata summaries of all saved JSON files on disk.

---

### 3. Get Scraped Document by ID
**`GET /api/v1/scraping/documents/{doc_id}`**

Fetches the complete structured JSON payload of a previously scraped document.

---

### 4. Delete Stored Document
**`DELETE /api/v1/scraping/documents/{doc_id}`**

Deletes a document JSON file from `data/scraped/`.

---

## 📦 Hugging Face Model Downloader Script

Use `scripts/download_models.py` to download and verify Hugging Face embedding and LLM models locally for offline RAG inference:

```powershell
# 1. Download default embedding model (BAAI/bge-small-en-v1.5) with automatic verification:
python scripts/download_models.py --embedding-model BAAI/bge-small-en-v1.5 --verify

# 2. Download a lightweight LLM model (Qwen/Qwen2.5-0.5B-Instruct):
python scripts/download_models.py --llm-model Qwen/Qwen2.5-0.5B-Instruct

# 3. Download both embedding and LLM models at once:
python scripts/download_models.py --all --verify
```

---

## 📮 Postman Collection

A pre-configured Postman Collection is included: [`CrawlRAG.postman_collection.json`](file:///d:/data-scraping/CrawlRAG.postman_collection.json).

### How to Import:
1. Open **Postman**.
2. Click **Import** (top-left).
3. Select `d:\data-scraping\CrawlRAG.postman_collection.json`.
4. Run the request **`⚡ Scrape & Auto-Crawl Website (Full Accuracy)`**!

---

## 📄 Stored JSON Schema Example

Each scraped page is saved in `data/scraped/{doc_id}.json` with this complete schema:

```json
{
  "id": "doc_9ac7a57aaf67",
  "url": "https://humanixtechnologies.com/",
  "title": "Humanix Technologies",
  "description": "Web site created using create-react-app",
  "raw_markdown": "# Humanix Technologies\n\n## Hire On Demand Developers...\n\n##### IT Consulting...",
  "clean_text": "Humanix Technologies\nHire On Demand Developers...",
  "sections": [
    {
      "heading": "IT Consulting",
      "level": 5,
      "content": "Humanix Technologies streamline complexity to deliver digital success..."
    },
    {
      "heading": "Permanent Staffing",
      "level": 5,
      "content": "With a talent pool of over 2,000 top-tier professionals..."
    }
  ],
  "internal_links": [
    "https://humanixtechnologies.com/IT-consulting",
    "https://humanixtechnologies.com/Permanent-staffing",
    "https://humanixtechnologies.com/about"
  ],
  "external_links": [
    "https://api.whatsapp.com/..."
  ],
  "content_hash": "cf25dd55118c0474a731bc581bc52d15b2c8590f7c3e235047feb6754d10294c",
  "depth": 0,
  "status_code": 200,
  "scraped_at": "2026-08-12T10:05:25.123456Z",
  "metadata": {
    "parser": "beautifulsoup4",
    "character_count": 3405,
    "word_count": 480,
    "section_count": 25,
    "internal_link_count": 15,
    "external_link_count": 5
  }
}
```

---

## 🧪 Run Automated Tests

```powershell
python tests/test_scraping_module.py
```

---

## 🚀 Next Phases
* **Module 2**: Parent-child and header-aware chunking from the saved JSON files into local Vector DB embeddings.
* **Module 3**: FastAPI RAG retrieval pipeline with token streaming for real-time AI Chatbot responses.
