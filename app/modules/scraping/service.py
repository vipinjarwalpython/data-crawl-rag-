import time
from typing import Dict, List, Optional, Tuple
from app.core.logging import logger
from app.modules.scraping.crawler import crawler
from app.modules.scraping.json_store import json_store
from app.modules.scraping.schemas import (
    DocumentListResponse,
    ScrapedDocument,
    UnifiedScrapeRequest,
    UnifiedScrapeResponse
)


class ScrapingService:
    """Unified Scraping Orchestrator: Handles single-page, multi-page, and recursive crawling."""

    def __init__(self):
        self.crawler = crawler
        self.json_store = json_store

    async def scrape_website(self, request: UnifiedScrapeRequest) -> UnifiedScrapeResponse:
        """Primary Unified Endpoint Logic:

        1. Takes 1 seed URL.
        2. Renders dynamic JavaScript / React SPA.
        3. Extracts main page content + all internal links.
        4. Recursively visits and scrapes each discovered internal URL.
        5. Saves every individual page into its own JSON file in data/scraped/.
        6. Returns all complete scraped documents in the response.
        """
        start_time = time.perf_counter()
        logger.info(
            f"Starting unified scrape on: {request.url} | Max Depth: {request.max_depth} | "
            f"Max Pages: {request.max_pages} | Render JS: {request.render_js}"
        )

        all_documents: List[ScrapedDocument] = []

        async def handle_document_saved(doc: ScrapedDocument):
            saved_doc, _ = await self.json_store.save_document(doc)

        scraped_docs, failed_urls, total_discovered = await self.crawler.crawl_nested(
            request=request,
            on_document_scraped=handle_document_saved
        )

        elapsed = round(time.perf_counter() - start_time, 2)

        logger.info(
            f"Unified scrape completed: {len(scraped_docs)} pages scraped from {request.url} in {elapsed}s"
        )

        return UnifiedScrapeResponse(
            seed_url=request.url,
            total_scraped=len(scraped_docs),
            total_discovered=total_discovered,
            total_failed=len(failed_urls),
            elapsed_seconds=elapsed,
            documents=scraped_docs,
            failed_urls=failed_urls
        )

    async def get_document(self, doc_id: str) -> Optional[ScrapedDocument]:
        """Fetch a specific JSON document by ID."""
        return await self.json_store.get_document(doc_id)

    async def list_all_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        query: Optional[str] = None
    ) -> DocumentListResponse:
        """List summaries of stored JSON documents."""
        documents, total_count = await self.json_store.list_documents(
            skip=skip,
            limit=limit,
            query=query
        )
        return DocumentListResponse(
            total_count=total_count,
            documents=documents
        )

    async def delete_document(self, doc_id: str) -> bool:
        """Delete document JSON file."""
        return await self.json_store.delete_document(doc_id)


scraping_service = ScrapingService()
