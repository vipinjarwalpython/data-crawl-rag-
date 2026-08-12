# 🕷️ CrawlRAG - Module 1: Web Scraping, Recursive Crawler & JSON Storage

**CrawlRAG** is a production-grade, modular FastAPI system designed to scrape websites, crawl nested links recursively, convert HTML into structured JSON and clean Markdown, and prepare data for Vector Embeddings and RAG Chatbots.

---

## 📁 Project Structure

```text
data-scraping/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI entry point & lifespan manager
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic BaseSettings (.env loader & path manager)
│   │   └── logging.py                 # Structured logger
│   └── modules/
│       ├── __init__.py
│       └── scraping/                  # MODULE 1: Web Scraping & Storage
│           ├── __init__.py
│           ├── schemas.py             # Pydantic schemas (Requests, Responses, JSON Document)
│           ├── parsers.py             # BeautifulSoup parser (Boilerplate removal, Clean Markdown, Links)
│           ├── crawler.py             # Async BFS Recursive Crawler with concurrency & rate limiting
│           ├── json_store.py          # JSON Document File Store & SHA-256 Hasher
│           ├── service.py             # Orchestration service for single/nested scraping
│           └── router.py              # REST API endpoints (/page, /crawl, /documents)
│
├── scripts/
│   └── download_models.py             # Hugging Face downloader for embeddings & LLM models
│
├── data/
│   └── scraped/                       # JSON document storage location
│
├── models/                            # Local directory for cached Hugging Face models
│   ├── embeddings/                    # Downloaded sentence transformers / vector models
│   └── llm/                           # Downloaded LLM tokenizers / weights
│
├── requirements.txt                   # Production Python dependencies
├── .env.example                       # Configuration template
└── README.md
```

---

## ⚡ Quickstart & Setup

### 1. Install Dependencies
Activate your virtual environment and install the required packages:

```bash
# Windows PowerShell
.\venv\Scripts\pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` (already done by default):
```bash
cp .env.example .env
```

### 3. Start the FastAPI Server
```bash
..\venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger UI: **http://127.0.0.1:8000/docs**
- ReDoc UI: **http://127.0.0.1:8000/redoc**
- Health Check: **http://127.0.0.1:8000/health**

---

## 🌐 Single Unified API Endpoint (Module 1)

### `POST /api/v1/scraping/scrape`

**One single endpoint for everything**:
1. You provide **1 URL** (e.g. `https://humanixtechnologies.com/`).
2. Renders dynamic JavaScript / React / Next.js client-side SPAs via headless Playwright Chromium.
3. Extracts all text words, clean markdown, and hierarchical headings (`h1`-`h6`) with full accuracy.
4. Automatically discovers all internal links (`<a href="...">`) on that page.
5. Automatically traverses and scrapes each discovered subpage recursively up to `max_depth` and `max_pages`.
6. Saves each page into its own individual JSON file in `data/scraped/`.
7. Directly returns the **full structured JSON data of all scraped pages** in the response body.

**Request Body:**
```json
{
  "url": "https://humanixtechnologies.com/",
  "max_depth": 2,
  "max_pages": 10,
  "render_js": true,
  "wait_seconds": 2.5,
  "concurrency": 2,
  "delay_seconds": 0.5,
  "force_refresh": true
}
```

*Note: If you only want to scrape a single page without following links, set `"max_depth": 0` or `"max_pages": 1`.*

---

### 3. List All Saved JSON Documents
**`GET /api/v1/scraping/documents?skip=0&limit=50&query=tutorial`**

Returns lightweight metadata summaries of all saved JSON files on disk.

---

### 4. Get a Specific Stored Document
**`GET /api/v1/scraping/documents/{doc_id}`**

Fetches the complete structured JSON representation of a scraped document.

---

### 5. Delete a Stored Document
**`DELETE /api/v1/scraping/documents/{doc_id}`**

Deletes a document JSON file from `data/scraped/`.

---

## 📦 Hugging Face Model Downloader Script

Use `scripts/download_models.py` to download and verify Hugging Face embedding and LLM models locally so they can run completely offline without API fees:

```bash
# 1. Download default embedding model (BAAI/bge-small-en-v1.5) with automatic verification
.\venv\Scripts\python scripts/download_models.py --embedding-model BAAI/bge-small-en-v1.5 --verify

# 2. Download a lightweight Hugging Face LLM (e.g., Qwen2.5-0.5B-Instruct)
.\venv\Scripts\python scripts/download_models.py --llm-model Qwen/Qwen2.5-0.5B-Instruct

# 3. Download both embedding and LLM models at once
.\venv\Scripts\python scripts/download_models.py --all
```

Downloaded models will be neatly cached in:
- `models/embeddings/{model_name}/`
- `models/llm/{model_name}/`

---

## 📄 Stored JSON Document Format Example

Each scraped page is saved as a JSON file (`data/scraped/doc_XXXXXXXXXXXX.json`) adhering to this schema:

```json
{
  "id": "doc_a1b2c3d4e5f6",
  "url": "https://docs.python.org/3/tutorial/index.html",
  "title": "The Python Tutorial — Python 3 Documentation",
  "description": "Python is an easy to learn, powerful programming language...",
  "raw_markdown": "# The Python Tutorial\n\nPython is an easy to learn...",
  "clean_text": "The Python Tutorial\nPython is an easy to learn...",
  "sections": [
    {
      "heading": "Whetting Your Appetite",
      "level": 2,
      "content": "If you do much work on computers, eventually you find that..."
    }
  ],
  "internal_links": [
    "https://docs.python.org/3/tutorial/appetite.html",
    "https://docs.python.org/3/tutorial/interpreter.html"
  ],
  "external_links": [],
  "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "depth": 1,
  "status_code": 200,
  "scraped_at": "2026-08-12T13:55:00Z",
  "metadata": {
    "parser": "beautifulsoup4",
    "character_count": 4820,
    "section_count": 6,
    "internal_link_count": 18,
    "external_link_count": 0
  }
}
```

---

## 🚀 Next Phases (Modules 2 & 3)
- **Module 2**: Header-aware & parent-child chunking from the saved JSON files into local Vector DB embeddings.
- **Module 3**: FastAPI RAG retrieval pipeline with token streaming for real-time AI Chatbot responses.
