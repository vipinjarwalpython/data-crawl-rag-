"""
Scraping orchestration service for CrawlRAG.

Wraps AsyncCrawler and JSONStore into a single high-level interface
for the scraping router.  Handles save callbacks, timing, and error logging.
"""

import time
from typing import List, Optional, Tuple

from app.core.logging import get_module_logger
from app.modules.scraping.crawler import crawler
from app.modules.scraping.json_store import json_store
from app.modules.scraping.schemas import (
    DocumentListResponse,
    ScrapedDocument,
    UnifiedScrapeRequest,
    UnifiedScrapeResponse,
)

logger = get_module_logger(__name__)


class ScrapingService:
    """Unified scraping orchestrator for single-page and recursive crawling."""

    def __init__(self) -> None:
        self.crawler = crawler
        self.json_store = json_store

    async def scrape_website(self, request: UnifiedScrapeRequest) -> UnifiedScrapeResponse:
        """Crawl *request.url* recursively and persist each page as a JSON document.

        Steps:
        1. BFS crawl from seed URL up to ``max_depth`` / ``max_pages``.
        2. Each page is parsed into a ``ScrapedDocument``.
        3. Documents are saved immediately via the ``on_document_scraped`` callback.
        4. Returns a ``UnifiedScrapeResponse`` with full document list and metrics.
        """
        start_time = time.perf_counter()
        logger.info(
            "Starting scrape: url='%s', max_depth=%d, max_pages=%d, render_js=%s.",
            request.url,
            request.max_depth,
            request.max_pages,
            request.render_js,
        )

        async def _save_document_callback(scraped_doc: ScrapedDocument) -> None:
            """Persist a scraped document immediately and log any save errors."""
            try:
                _saved_doc, was_new = await self.json_store.save_document(scraped_doc)
                if was_new:
                    logger.debug("Saved new document: '%s' (%s).", scraped_doc.id, scraped_doc.url)
                else:
                    logger.debug("Document unchanged, skipped rewrite: '%s'.", scraped_doc.id)
            except Exception as save_exc:
                logger.error(
                    "Failed to save document '%s' (%s): %s",
                    scraped_doc.id,
                    scraped_doc.url,
                    save_exc,
                    exc_info=True,
                )

        scraped_documents, failed_urls, total_discovered_count = await self.crawler.crawl_nested(
            request=request,
            on_document_scraped=_save_document_callback,
        )

        elapsed = round(time.perf_counter() - start_time, 2)
        logger.info(
            "Scrape complete: scraped=%d, discovered=%d, failed=%d, elapsed=%.2fs.",
            len(scraped_documents),
            total_discovered_count,
            len(failed_urls),
            elapsed,
        )

        return UnifiedScrapeResponse(
            seed_url=request.url,
            total_scraped=len(scraped_documents),
            total_discovered=total_discovered_count,
            total_failed=len(failed_urls),
            elapsed_seconds=elapsed,
            documents=scraped_documents,
            failed_urls=failed_urls,
        )

    async def get_document(self, doc_id: str) -> Optional[ScrapedDocument]:
        """Retrieve a scraped document by its ``doc_id``."""
        return await self.json_store.get_document(doc_id)

    async def list_all_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        query: Optional[str] = None,
    ) -> DocumentListResponse:
        """Return paginated summaries of all stored scraped documents."""
        paginated_documents, total_count = await self.json_store.list_documents(
            skip=skip,
            limit=limit,
            query=query,
        )
        return DocumentListResponse(
            total_count=total_count,
            documents=paginated_documents,
        )

    async def delete_document(self, doc_id: str) -> bool:
        """Delete the stored JSON file for *doc_id*.  Returns True on success."""
        return await self.json_store.delete_document(doc_id)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
scraping_service = ScrapingService()
