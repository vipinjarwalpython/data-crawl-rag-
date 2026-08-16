# 🐍 CrawlRAG Backend (FastAPI + AI Pipeline)

This directory contains the entire Python backend for CrawlRAG.

---

## ⚡ Quick Start

### 1. Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
playwright install chromium
```

### 3. Start FastAPI Server
```powershell
uvicorn app.main:app --reload --port 8000
```

* **Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 📁 Directory Structure
* `app/` — Application source code (core settings, logging, scraping & RAG modules)
* `data/` — Storage for scraped JSON, cleaned text, chunks, and vector store
* `models/` — Local cached models (`BAAI/bge-small-en-v1.5` & `Qwen/Qwen2.5-1.5B-Instruct`)
* `logs/` — Rotating server log files (`crawlrag.log`)
* `scripts/` — Utility scripts (e.g. `download_models.py`)
* `tests/` — Automated test suite
* `CrawlRAG.postman_collection.json` — Postman API collection
