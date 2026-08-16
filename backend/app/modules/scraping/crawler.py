import asyncio
import sys
import time
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_module_logger
from app.modules.scraping.parsers import HTMLParser
from app.modules.scraping.schemas import ScrapedDocument, UnifiedScrapeRequest

logger = get_module_logger(__name__)


def _render_page_sync(
    url: str,
    wait_seconds: float,
    user_agent: str,
    timeout_seconds: float,
    custom_headers: Optional[Dict[str, str]] = None
) -> Tuple[str, int]:
    """Thread-safe Playwright renderer that runs independently of the asyncio event loop.

    Guarantees 100% compatibility on Windows with Uvicorn without NotImplementedError.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1440, "height": 900},
            extra_http_headers=custom_headers or {}
        )
        page = context.new_page()
        
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=int(timeout_seconds * 1000)
        )
        status_code = response.status if response else 200

        # Progressive scrolling to trigger lazy-loaded React components & testimonials
        try:
            for i in range(1, 5):
                page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/4})")
                page.wait_for_timeout(300)
        except Exception:
            pass

        # Wait for dynamic JS/React hydration
        if wait_seconds > 0:
            page.wait_for_timeout(int(wait_seconds * 1000))

        content = page.content()
        browser.close()
        return content, status_code


class AsyncCrawler:
    """Production Async Crawler supporting both high-speed static scraping (HTTPX)

    and dynamic JavaScript / React SPA rendering (Playwright).
    """

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.user_agent = user_agent or settings.DEFAULT_USER_AGENT
        self.timeout_seconds = timeout_seconds or settings.REQUEST_TIMEOUT_SECONDS

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Construct request headers with browser user-agent."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive"
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    async def fetch_static_html(
        self,
        client: httpx.AsyncClient,
        url: str
    ) -> Tuple[str, int]:
        """Fetch raw static HTML content with HTTPX."""
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text, response.status_code

    async def fetch_rendered_html(
        self,
        url: str,
        wait_seconds: float = 2.0,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> Tuple[str, int]:
        """Execute Playwright in a dedicated worker thread for non-blocking, crash-free rendering on Windows."""
        try:
            return await asyncio.to_thread(
                _render_page_sync,
                url,
                wait_seconds,
                self.user_agent,
                self.timeout_seconds,
                custom_headers
            )
        except Exception as e:
            logger.error(f"Playwright rendering error for {url}: {e}. Falling back to static HTTPX...")
            async with httpx.AsyncClient(headers=self._get_headers(custom_headers), timeout=self.timeout_seconds) as client:
                return await self.fetch_static_html(client, url)

    async def scrape_single_url(
        self,
        url: str,
        render_js: bool = True,
        wait_seconds: float = 2.0,
        custom_headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> ScrapedDocument:
        """Scrape and parse a single page URL with dynamic or static engine."""
        timeout_val = timeout or self.timeout_seconds

        if render_js:
            html_content, status_code = await self.fetch_rendered_html(
                url=url,
                wait_seconds=wait_seconds,
                custom_headers=custom_headers
            )
        else:
            headers = self._get_headers(custom_headers)
            async with httpx.AsyncClient(headers=headers, timeout=timeout_val) as client:
                html_content, status_code = await self.fetch_static_html(client, url)

        doc = HTMLParser.parse_html(
            html_content=html_content,
            url=url,
            depth=0,
            status_code=status_code
        )

        # Auto-healing: If static scrape yielded empty text on React SPA, auto-render with Playwright
        if len(doc.clean_text.strip()) < 50 and not render_js:
            logger.info(f"Page {url} has minimal text ({len(doc.clean_text)} chars). Auto-rendering with Playwright...")
            html_content, status_code = await self.fetch_rendered_html(url=url, wait_seconds=wait_seconds or 2.5)
            doc = HTMLParser.parse_html(html_content=html_content, url=url, depth=0, status_code=status_code)

        return doc

    def _is_url_allowed(
        self,
        url: str,
        allowed_domains: Set[str],
        base_path: str,
        stay_within_path: bool,
        allow_external: bool = False
    ) -> bool:
        """Check if URL matches domain and path criteria."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check domain
            if not allow_external and domain not in allowed_domains:
                return False

            # Ignore common binary/media extensions
            disallowed_extensions = (
                ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
                ".zip", ".tar", ".gz", ".exe", ".mp4", ".mp3", ".wav",
                ".css", ".js", ".json", ".xml", ".ico"
            )
            if any(parsed.path.lower().endswith(ext) for ext in disallowed_extensions):
                return False

            # Check path boundary if enabled
            if not allow_external and stay_within_path and base_path and base_path != "/":
                if not parsed.path.startswith(base_path):
                    return False

            return True
        except Exception:
            return False

    async def crawl_nested(
        self,
        request: UnifiedScrapeRequest,
        on_document_scraped = None
    ) -> Tuple[List[ScrapedDocument], List[Dict[str, str]], int]:
        """Execute automated BFS recursive crawling from the seed URL.

        Discovers links on each page, renders JavaScript if requested, visits them,
        and returns all scraped documents and error logs.
        """
        seed_url = HTMLParser.normalize_url(request.url, request.url) or request.url
        seed_parsed = urlparse(seed_url)
        seed_domain = seed_parsed.netloc.lower()
        base_path = seed_parsed.path.rstrip("/")

        allowed_domains = {seed_domain}

        visited_urls: Set[str] = set()
        queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        await queue.put((seed_url, 0))
        visited_urls.add(seed_url)

        scraped_docs: List[ScrapedDocument] = []
        failed_urls: List[Dict[str, str]] = []
        total_discovered = 1

        semaphore = asyncio.Semaphore(request.concurrency)
        headers = self._get_headers()

        logger.info(
            f"Starting crawl on seed: {seed_url} | Max Depth: {request.max_depth} | "
            f"Max Pages: {request.max_pages} | Render JS: {request.render_js} | Concurrency: {request.concurrency}"
        )

        httpx_client = None
        if not request.render_js:
            httpx_client = httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds)

        try:
            while not queue.empty() and len(scraped_docs) < request.max_pages:
                current_url, depth = await queue.get()

                async with semaphore:
                    try:
                        logger.debug(f"[Depth {depth}] Scraping: {current_url}")
                        
                        if request.render_js:
                            html_content, status_code = await self.fetch_rendered_html(
                                url=current_url,
                                wait_seconds=request.wait_seconds
                            )
                        else:
                            html_content, status_code = await self.fetch_static_html(
                                httpx_client,
                                current_url
                            )

                        doc = HTMLParser.parse_html(
                            html_content=html_content,
                            url=current_url,
                            depth=depth,
                            status_code=status_code
                        )

                        # Auto-Healing: If static scraping yielded empty/minimal text, auto-render with Playwright
                        if len(doc.clean_text.strip()) < 50 and not request.render_js:
                            logger.info(f"Page {current_url} yielded minimal text ({len(doc.clean_text)} chars). Auto-rendering with Playwright...")
                            html_content, status_code = await self.fetch_rendered_html(
                                url=current_url,
                                wait_seconds=request.wait_seconds or 2.5
                            )
                            doc = HTMLParser.parse_html(
                                html_content=html_content,
                                url=current_url,
                                depth=depth,
                                status_code=status_code
                            )

                        scraped_docs.append(doc)

                        # Trigger callback (e.g. saving to disk immediately)
                        if on_document_scraped:
                            await on_document_scraped(doc)

                        # Enqueue newly discovered links if depth limit allows
                        if depth < request.max_depth:
                            crawl_external = getattr(request, "crawl_external_links", True)
                            links_to_crawl = list(doc.internal_links)
                            if crawl_external:
                                links_to_crawl.extend(doc.external_links)

                            for link in links_to_crawl:
                                normalized_link = HTMLParser.normalize_url(link, current_url)
                                if not normalized_link:
                                    continue

                                if normalized_link not in visited_urls:
                                    if self._is_url_allowed(
                                        normalized_link,
                                        allowed_domains,
                                        base_path,
                                        request.stay_within_path,
                                        allow_external=crawl_external
                                    ):
                                        visited_urls.add(normalized_link)
                                        total_discovered += 1
                                        await queue.put((normalized_link, depth + 1))

                        # Respect polite delay
                        if request.delay_seconds > 0:
                            await asyncio.sleep(request.delay_seconds)

                    except Exception as e:
                        logger.warning(f"Failed to scrape {current_url}: {e}")
                        failed_urls.append({"url": current_url, "error": str(e)})

                    finally:
                        queue.task_done()

        finally:
            if httpx_client:
                await httpx_client.aclose()

        logger.info(
            f"Crawl completed. Scraped: {len(scraped_docs)} | Discovered: {total_discovered} | "
            f"Failed: {len(failed_urls)}"
        )
        return scraped_docs, failed_urls, total_discovered


crawler = AsyncCrawler()
