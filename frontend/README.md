# 🤖 CrawlRAG Web UI (React + Vite)

A modern, classic, dark-themed AI Chatbot & Ingestion Dashboard for CrawlRAG.

---

## ⚡ Quick Start

### 1. Make sure your FastAPI backend is running:
In your main project folder:
```powershell
uvicorn app.main:app --reload --port 8000
```

### 2. Start the Frontend Dashboard:
In this `frontend/` folder:
```powershell
cd frontend
npm install
npm run dev
```

Open your browser at:
👉 **[http://localhost:5173](http://localhost:5173)**

---

## 🌟 Features

* **1-Click Ingest & Index**: Enter any website URL (e.g. `https://books.toscrape.com/`), choose depth, and click *Ingest & Index*.
* **Visual Progress Stepper**: Real-time feedback through Crawl ➔ Clean ➔ Chunk ➔ Vector Embedding stages.
* **Knowledge Chatbot**: Ask questions with instant context retrieval powered by `BAAI/bge-small-en-v1.5` and generation via `Qwen/Qwen2.5-1.5B-Instruct`.
* **Interactive Citations Drawer**: Clickable source badge pills showing exact chunk text and percentage match scores.
* **Smart Search Reframing**: Toggleable LLM search query optimization for better recall.
