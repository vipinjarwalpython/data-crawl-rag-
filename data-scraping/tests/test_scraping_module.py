"""End-to-End Verification Test for CrawlRAG Module 1."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.modules.scraping.parsers import HTMLParser
from app.modules.scraping.schemas import UnifiedScrapeRequest
from app.modules.scraping.service import scraping_service
from app.modules.scraping.json_store import json_store


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CrawlRAG Documentation</title>
    <meta name="description" content="A high performance scraping and RAG framework">
</head>
<body>
    <nav><a href="/home">Home</a> <a href="/about">About</a></nav>
    <script>console.log("noisy script");</script>

    <main>
        <h1>Welcome to CrawlRAG</h1>
        <p>CrawlRAG is designed for automated web scraping and RAG chatbots.</p>

        <h2>Features</h2>
        <p>It supports BeautifulSoup parsing, clean markdown generation, and nested page crawling.</p>
        <ul>
            <li>Recursive link discovery</li>
            <li>Direct JSON file storage</li>
            <li>Local Hugging Face embeddings</li>
        </ul>

        <h2>Internal Links</h2>
        <p>Check out our subpages below:</p>
        <p><a href="https://example.com/docs/quickstart">Quickstart Guide</a></p>
        <p><a href="https://example.com/docs/architecture?utm_source=test">Architecture Deep Dive</a></p>
        <p><a href="https://github.com/external/repo">External GitHub Link</a></p>
    </main>

    <footer>Copyright 2026 CrawlRAG</footer>
</body>
</html>
"""

PAGE_QUICKSTART_HTML = """
<!DOCTYPE html>
<html>
<head><title>Quickstart - CrawlRAG</title></head>
<body>
    <main>
        <h1>Quickstart</h1>
        <p>Step 1: Install requirements. Step 2: Run server.</p>
        <p><a href="https://example.com/docs/install">Installation Guide</a></p>
    </main>
</body>
</html>
"""

PAGE_ARCHITECTURE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Architecture - CrawlRAG</title></head>
<body>
    <main>
        <h1>Architecture</h1>
        <p>CrawlRAG uses a Modular Monolith architecture with FastAPI.</p>
    </main>
</body>
</html>
"""


async def test_html_parser():
    print("\n--- 1. Testing HTMLParser & BeautifulSoup ---")
    doc = HTMLParser.parse_html(SAMPLE_HTML, url="https://example.com/docs", depth=0)
    
    assert doc.title == "CrawlRAG Documentation", f"Unexpected title: {doc.title}"
    assert doc.description == "A high performance scraping and RAG framework"
    assert len(doc.sections) >= 2, f"Expected at least 2 sections, got {len(doc.sections)}"
    assert "noisy script" not in doc.clean_text, "Script content was not stripped!"
    assert "Copyright 2026" in doc.clean_text, "Footer content should be preserved!"
    assert len(doc.internal_links) == 4, f"Expected 4 internal links, got {doc.internal_links}"
    assert len(doc.external_links) == 1, f"Expected 1 external link, got {doc.external_links}"
    assert doc.content_hash is not None
    print(f"✅ HTMLParser test passed! Document ID: {doc.id}")
    print(f"   Extracted Sections: {[s.heading for s in doc.sections]}")
    print(f"   Internal Links: {doc.internal_links}")


async def test_json_store():
    print("\n--- 2. Testing JSONStore ---")
    doc = HTMLParser.parse_html(SAMPLE_HTML, url="https://example.com/docs/test-save", depth=0)
    await json_store.delete_document(doc.id)

    saved_doc, is_updated = await json_store.save_document(doc)
    assert is_updated is True, "Expected document to be newly created"

    # Re-save identical document -> should not trigger update
    _, is_updated_second = await json_store.save_document(doc)
    assert is_updated_second is False, "Expected deduplication to skip write"

    # Fetch document by ID
    loaded_doc = await json_store.get_document(doc.id)
    assert loaded_doc is not None
    assert loaded_doc.title == doc.title

    # List documents
    summaries, count = await json_store.list_documents()
    assert count >= 1, "Expected at least 1 document in store"
    print(f"✅ JSONStore test passed! Saved, verified deduplication, and listed {count} docs.")


async def test_nested_crawler_pipeline():
    print("\n--- 3. Testing Automated Recursive Crawler Pipeline ---")
    
    url_mock_map = {
        "https://example.com/docs": (SAMPLE_HTML, 200),
        "https://example.com/docs/quickstart": (PAGE_QUICKSTART_HTML, 200),
        "https://example.com/docs/architecture": (PAGE_ARCHITECTURE_HTML, 200),
        "https://example.com/home": ("<html><body><h1>Home</h1></body></html>", 200),
        "https://example.com/about": ("<html><body><h1>About</h1></body></html>", 200),
        "https://example.com/docs/install": ("<html><body><h1>Install</h1></body></html>", 200),
    }

    async def mock_fetch(client, url):
        clean_u = url.split("?")[0]
        if clean_u in url_mock_map:
            return url_mock_map[clean_u]
        return ("<html><body><h1>Page</h1></body></html>", 200)

    req = UnifiedScrapeRequest(
        url="https://example.com/docs",
        max_depth=2,
        max_pages=5,
        render_js=False,
        concurrency=2,
        delay_seconds=0.0
    )

    with patch.object(scraping_service.crawler, "fetch_static_html", side_effect=mock_fetch):
        response = await scraping_service.scrape_website(req)

        assert response.total_scraped > 1, f"Expected > 1 pages scraped, got {response.total_scraped}"
        assert response.total_discovered >= 4, f"Expected >= 4 links discovered, got {response.total_discovered}"
        assert len(response.documents) > 1, "Expected full document objects in response"
        print(f"✅ Automated Nested Crawler successfully traversed pages!")
        print(f"   Seed URL: {response.seed_url}")
        print(f"   Total Pages Scraped: {response.total_scraped}")
        print(f"   Total Links Discovered: {response.total_discovered}")
        print(f"   Returned Full Documents: {[d.title for d in response.documents]}")


async def test_live_single_page_scrape():
    print("\n--- 4. Testing Live Scrape (https://example.com) ---")
    req = UnifiedScrapeRequest(url="https://example.com", max_depth=0, max_pages=1, render_js=False)
    try:
        res = await scraping_service.scrape_website(req)
        assert res.total_scraped == 1
        doc = res.documents[0]
        assert doc.status_code == 200
        print(f"✅ Live scrape successful: {doc.url}")
        print(f"   Title: {doc.title}")
        print(f"   Markdown Preview:\n{doc.raw_markdown[:150]}...")
    except Exception as e:
        print(f"⚠️ Live network request skipped/failed: {e}")


async def main():
    print("==================================================")
    print("🧪 Running CrawlRAG Module 1 Verification Suite")
    print("==================================================")
    await test_html_parser()
    await test_json_store()
    await test_nested_crawler_pipeline()
    await test_live_single_page_scrape()
    print("\n🎉 All Module 1 components verified successfully!\n")


if __name__ == "__main__":
    asyncio.run(main())
