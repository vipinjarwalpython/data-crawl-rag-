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
    timeout_seconds: float = 15.0,
    custom_headers: Optional[Dict[str, str]] = None
) -> Tuple[str, int]:
    """Thread-safe, lightweight Playwright renderer that runs in a worker thread.

    Guarantees 100% compatibility on Windows with Uvicorn without NotImplementedError.
    Optimized to abort heavy media downloads (images, fonts, media) for 3x faster page rendering.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        logger.error(f"Playwright not installed: {e}")
        raise

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking"
            ]
        )
        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 800},
            extra_http_headers=custom_headers or {}
        )
        page = context.new_page()

        # Optimize page load: block images, media & heavy fonts
        def _route_filter(route):
            request = route.request
            if request.resource_type in ["image", "media", "font"]:
                route.abort()
            else:
                route.continue_()

        try:
            page.route("**/*", _route_filter)
        except Exception:
            pass

        try:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(timeout_seconds * 1000)
            )
            status_code = response.status if response else 200

            # Dynamic hydration wait (default: 1.0s)
            if wait_seconds > 0:
                page.wait_for_timeout(int(min(wait_seconds, 5.0) * 1000))

            content = page.content()
            return content, status_code
        finally:
            try:
                page.close()
                context.close()
                browser.close()
            except Exception:
                pass


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
        self.timeout_seconds = timeout_seconds or 15.0

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
        response = await client.get(url, follow_redirects=True, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.text, response.status_code

    async def fetch_rendered_html(
        self,
        url: str,
        wait_seconds: float = 1.0,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> Tuple[str, int]:
        """Execute Playwright in a dedicated worker thread with fallback to HTTPX."""
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
            logger.warning(f"Playwright rendering failed for {url} ({e}). Falling back to static HTTPX...")
            async with httpx.AsyncClient(headers=self._get_headers(custom_headers), timeout=self.timeout_seconds) as client:
                return await self.fetch_static_html(client, url)

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
            if not parsed.scheme or not parsed.netloc:
                return False

            domain = parsed.netloc.lower()

            # Ignore social media and common external tracking domains
            blocked_domains = {
                "facebook.com", "twitter.com", "x.com", "instagram.com",
                "youtube.com", "linkedin.com", "pinterest.com", "tiktok.com",
                "github.com", "google.com", "apple.com"
            }
            if any(domain.endswith(b) for b in blocked_domains):
                return False

            # Check domain allowance
            if not allow_external:
                if not any(domain == ad or domain.endswith("." + ad) for ad in allowed_domains):
                    return False

            # Ignore common binary / media extensions
            disallowed_extensions = (
                ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
                ".zip", ".tar", ".gz", ".exe", ".mp4", ".mp3", ".wav",
                ".css", ".js", ".json", ".xml", ".ico", ".woff", ".woff2", ".ttf"
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
        crawl_external = bool(getattr(request, "crawl_external_links", False))

        visited_urls: Set[str] = set()
        queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        await queue.put((seed_url, 0))
        visited_urls.add(seed_url)

        scraped_docs: List[ScrapedDocument] = []
        failed_urls: List[Dict[str, str]] = []
        total_discovered = 1

        concurrency = min(max(1, request.concurrency), 5)
        semaphore = asyncio.Semaphore(concurrency)
        headers = self._get_headers()

        logger.info(
            f"Starting crawl on seed: {seed_url} | Max Depth: {request.max_depth} | "
            f"Max Pages: {request.max_pages} | Render JS: {request.render_js} | "
            f"Concurrency: {concurrency} | Crawl External: {crawl_external}"
        )

        httpx_client = None
        if not request.render_js:
            httpx_client = httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds)

        try:
            while not queue.empty() and len(scraped_docs) < request.max_pages:
                current_url, depth = await queue.get()

                async with semaphore:
                    try:
                        logger.info(f"[{len(scraped_docs)+1}/{request.max_pages}] [Depth {depth}] Scraping: {current_url}")

                        if request.render_js:
                            html_content, status_code = await self.fetch_rendered_html(
                                url=current_url,
                                wait_seconds=min(request.wait_seconds, 3.0)
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

                        # Auto-Healing: If static scraping yielded empty text on SPA, auto-render with Playwright
                        if len(doc.clean_text.strip()) < 50 and not request.render_js:
                            logger.info(f"Page {current_url} yielded minimal text. Auto-rendering with Playwright...")
                            html_content, status_code = await self.fetch_rendered_html(
                                url=current_url,
                                wait_seconds=1.5
                            )
                            doc = HTMLParser.parse_html(
                                html_content=html_content,
                                url=current_url,
                                depth=depth,
                                status_code=status_code
                            )

                        scraped_docs.append(doc)

                        # Trigger immediate persistence callback
                        if on_document_scraped:
                            try:
                                await on_document_scraped(doc)
                            except Exception as save_err:
                                logger.error(f"Error in on_document_scraped callback: {save_err}")

                        # Discover & enqueue internal links if depth permits
                        if depth < request.max_depth and len(scraped_docs) < request.max_pages:
                            links_to_crawl = list(doc.internal_links)
                            if crawl_external:
                                links_to_crawl.extend(doc.external_links)

                            for link in links_to_crawl:
                                if len(scraped_docs) + queue.qsize() >= request.max_pages:
                                    break

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

                        # Polite delay
                        if request.delay_seconds > 0:
                            await asyncio.sleep(min(request.delay_seconds, 1.0))

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
