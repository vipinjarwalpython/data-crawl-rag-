from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UnifiedScrapeRequest(BaseModel):
    """Unified request model for single-page and automated nested crawling."""
    url: str = Field(
        ...,
        description="Seed URL to start scraping and link discovery from",
        example="https://humanixtechnologies.com/"
    )
    max_depth: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Recursion depth (0 = only main page, 1 = main + immediate links, 2 = 2 levels deep, etc.)"
    )
    max_pages: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum total pages to scrape across the website"
    )
    render_js: bool = Field(
        default=True,
        description="If true, uses headless Playwright Chromium to render dynamic JavaScript & React SPAs"
    )
    wait_seconds: float = Field(
        default=2.0,
        ge=0.0,
        le=15.0,
        description="Seconds to wait for client-side JavaScript execution and dynamic DOM loading"
    )
    concurrency: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of concurrent pages to scrape"
    )
    delay_seconds: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Polite delay between page requests"
    )
    stay_within_path: bool = Field(
        default=False,
        description="If true, only follows links matching the path prefix of the seed URL"
    )
    crawl_external_links: bool = Field(
        default=True,
        description="If true, recursively crawls external links discovered on any pages"
    )
    force_refresh: bool = Field(
        default=False,
        description="If true, re-scrapes even if cached JSON already exists"
    )


class ExtractedSection(BaseModel):
    """Hierarchical section containing heading and associated text."""
    heading: str = Field(..., description="Header text")
    level: int = Field(default=1, description="Header level (1 for h1, 2 for h2, etc.)")
    content: str = Field(..., description="Text content belonging to this section")


class ScrapedDocument(BaseModel):
    """Complete structured JSON schema for a scraped web page."""
    id: str = Field(..., description="Unique document ID (doc_hash)")
    url: str = Field(..., description="Source URL of the page")
    title: str = Field(..., description="Extracted HTML page title")
    description: Optional[str] = Field(default=None, description="Meta description if available")
    raw_markdown: str = Field(..., description="Clean markdown format of page content")
    clean_text: str = Field(..., description="Clean plain text of all words on page")
    sections: List[ExtractedSection] = Field(
        default_factory=list,
        description="Hierarchical sections for header-aware RAG chunking"
    )
    internal_links: List[str] = Field(
        default_factory=list,
        description="All discovered internal subpage URLs on the same domain"
    )
    external_links: List[str] = Field(
        default_factory=list,
        description="Discovered external URLs"
    )
    content_hash: str = Field(..., description="SHA-256 hash of the extracted text")
    depth: int = Field(default=0, description="Crawl depth at which this page was discovered")
    status_code: int = Field(default=200, description="HTTP response status code")
    scraped_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="UTC timestamp of the scrape"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Page metadata stats"
    )


class ScrapedDocumentSummary(BaseModel):
    """Lightweight summary of a stored document."""
    id: str
    url: str
    title: str
    content_hash: str
    scraped_at: str
    file_name: str
    file_size_bytes: int
    total_sections: int
    total_characters: int


class DocumentListResponse(BaseModel):
    """Response model for listing all stored JSON documents."""
    total_count: int
    documents: List[ScrapedDocumentSummary]


class UnifiedScrapeResponse(BaseModel):
    """Unified response containing full documents and crawl summary."""
    seed_url: str
    total_scraped: int
    total_discovered: int
    total_failed: int
    elapsed_seconds: float
    documents: List[ScrapedDocument] = Field(
        ...,
        description="Full structured JSON data for each scraped page"
    )
    failed_urls: List[Dict[str, str]] = Field(default_factory=list)
