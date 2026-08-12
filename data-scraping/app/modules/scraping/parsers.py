import hashlib
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup, Comment, Tag
from app.modules.scraping.schemas import ExtractedSection, ScrapedDocument


class HTMLParser:
    """Production HTML Parser extracting 100% of visible text, clean markdown,

    hierarchical headers, contact info, and internal/external hyperlinks.
    """

    # Only strip strictly non-visible or script elements (Preserve headers, footers, forms, navigation text)
    UNWANTED_TAGS = {
        "script", "style", "noscript", "svg", "iframe", "canvas", "template"
    }

    # Tracking query parameters to strip from discovered URLs
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "msclkid", "ref", "source"
    }

    @classmethod
    def clean_html_tree(cls, soup: BeautifulSoup) -> None:
        """Remove only non-visible script and styling tags from the DOM tree."""
        # Remove HTML comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove scripts, styles, svg
        for tag_name in cls.UNWANTED_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

    @classmethod
    def extract_title(cls, soup: BeautifulSoup, fallback: str = "") -> str:
        """Extract clean document title."""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            if title:
                return title
        
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
            
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        return fallback or "Untitled Page"

    @classmethod
    def extract_description(cls, soup: BeautifulSoup) -> Optional[str]:
        """Extract meta description if available."""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"].strip()

        return None

    @classmethod
    def extract_sections(cls, soup: BeautifulSoup) -> List[ExtractedSection]:
        """Extract hierarchical sections (heading + associated text content)."""
        sections: List[ExtractedSection] = []
        heading_tags = ["h1", "h2", "h3", "h4", "h5", "h6"]
        
        container = soup.find("body") or soup

        current_heading = "Overview"
        current_level = 1
        current_text_parts: List[str] = []

        for element in container.descendants:
            if isinstance(element, Tag):
                if element.name in heading_tags:
                    combined_text = " ".join(current_text_parts).strip()
                    if combined_text:
                        sections.append(ExtractedSection(
                            heading=current_heading,
                            level=current_level,
                            content=combined_text
                        ))
                    
                    current_heading = element.get_text(strip=True) or "Untitled Section"
                    try:
                        current_level = int(element.name[1])
                    except (ValueError, IndexError):
                        current_level = 1
                    current_text_parts = []
                elif element.name in ["p", "li", "blockquote", "td", "th", "div", "span", "a", "label"]:
                    # Only collect direct text or leaf text to avoid duplicating parent container text
                    if not any(isinstance(child, Tag) and child.name in ["p", "div", "section", "article"] for child in element.children):
                        text = element.get_text(strip=True)
                        if text and len(text) > 3 and text not in current_text_parts:
                            current_text_parts.append(text)

        combined_text = " ".join(current_text_parts).strip()
        if combined_text:
            sections.append(ExtractedSection(
                heading=current_heading,
                level=current_level,
                content=combined_text
            ))

        return sections

    @classmethod
    def extract_clean_text_and_markdown(cls, soup: BeautifulSoup, title: str) -> Tuple[str, str]:
        """Extract 100% of visible text and clean structured markdown."""
        body = soup.find("body") or soup

        # 1. Extract 100% complete clean text
        raw_full_text = body.get_text(separator="\n", strip=True)
        raw_lines = [line.strip() for line in raw_full_text.split("\n") if line.strip()]
        
        # Deduplicate consecutive identical lines while preserving exact order
        deduped_lines: List[str] = []
        for line in raw_lines:
            if not deduped_lines or deduped_lines[-1] != line:
                deduped_lines.append(line)
        clean_text = "\n".join(deduped_lines)

        # 2. Build structured markdown
        markdown_lines: List[str] = [f"# {title}\n"]

        for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "pre", "blockquote", "table", "address"]):
            tag = element.name
            raw_text = element.get_text(strip=True)
            if not raw_text:
                continue

            if tag.startswith("h"):
                try:
                    level = int(tag[1])
                except (ValueError, IndexError):
                    level = 2
                prefix = "#" * level
                markdown_lines.append(f"\n{prefix} {raw_text}\n")
            elif tag == "p":
                markdown_lines.append(f"\n{raw_text}\n")
            elif tag in ["ul", "ol"]:
                items = element.find_all("li")
                for item in items:
                    item_text = item.get_text(strip=True)
                    if item_text:
                        markdown_lines.append(f"- {item_text}")
            elif tag == "blockquote":
                markdown_lines.append(f"\n> {raw_text}\n")
            elif tag == "pre":
                markdown_lines.append(f"\n```\n{raw_text}\n```\n")
            elif tag == "address":
                markdown_lines.append(f"\n📍 **Address:** {raw_text}\n")

        raw_markdown = "\n".join(markdown_lines)
        raw_markdown = re.sub(r"\n{3,}", "\n\n", raw_markdown).strip()

        # If markdown missed body text (e.g. from div-only SPAs), augment with clean text
        if len(raw_markdown) < len(clean_text) * 0.5:
            raw_markdown = f"# {title}\n\n" + clean_text

        return clean_text, raw_markdown

    @classmethod
    def normalize_url(cls, raw_url: str, base_url: str) -> Optional[str]:
        """Normalize URL: join relative paths, strip fragments, remove tracking params."""
        if not raw_url or raw_url.startswith(("javascript:", "mailto:", "tel:", "#")):
            return None

        # Convert relative to absolute
        absolute_url = urljoin(base_url, raw_url.strip())
        parsed = urlparse(absolute_url)

        # Only allow HTTP / HTTPS
        if parsed.scheme not in ["http", "https"]:
            return None

        # Filter out tracking query params
        query_params = parse_qsl(parsed.query)
        cleaned_params = [
            (k, v) for k, v in query_params if k.lower() not in cls.TRACKING_PARAMS
        ]
        clean_query = urlencode(cleaned_params)

        # Strip fragment (#section) and rebuild URL
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") if parsed.path != "/" else "/",
            "",  # params
            clean_query,
            ""   # fragment
        ))

        return normalized

    @classmethod
    def extract_links(cls, soup: BeautifulSoup, base_url: str) -> Tuple[List[str], List[str]]:
        """Extract and categorize normalized internal and external hyperlinks."""
        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc.lower()

        internal_links_set: Set[str] = set()
        external_links_set: Set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href")
            normalized = cls.normalize_url(href, base_url)
            if not normalized:
                continue

            link_domain = urlparse(normalized).netloc.lower()
            if link_domain == base_domain:
                if normalized != base_url:
                    internal_links_set.add(normalized)
            else:
                external_links_set.add(normalized)

        return sorted(list(internal_links_set)), sorted(list(external_links_set))

    @classmethod
    def compute_hash(cls, content: str) -> str:
        """Compute SHA-256 hash of text content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def generate_doc_id(cls, url: str) -> str:
        """Generate a deterministic document ID based on URL hash."""
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        return f"doc_{url_hash}"

    @classmethod
    def parse_html(
        cls,
        html_content: str,
        url: str,
        depth: int = 0,
        status_code: int = 200
    ) -> ScrapedDocument:
        """Parse raw HTML string into a validated ScrapedDocument."""
        try:
            soup = BeautifulSoup(html_content, "lxml")
        except Exception:
            soup = BeautifulSoup(html_content, "html.parser")

        # Extract links before cleaning unwanted tags
        internal_links, external_links = cls.extract_links(soup, url)

        # Clean only non-visible script/style elements
        cls.clean_html_tree(soup)

        title = cls.extract_title(soup, fallback=url)
        description = cls.extract_description(soup)
        sections = cls.extract_sections(soup)
        clean_text, raw_markdown = cls.extract_clean_text_and_markdown(soup, title)
        content_hash = cls.compute_hash(clean_text)
        doc_id = cls.generate_doc_id(url)

        return ScrapedDocument(
            id=doc_id,
            url=url,
            title=title,
            description=description,
            raw_markdown=raw_markdown,
            clean_text=clean_text,
            sections=sections,
            internal_links=internal_links,
            external_links=external_links,
            content_hash=content_hash,
            depth=depth,
            status_code=status_code,
            metadata={
                "parser": "beautifulsoup4",
                "character_count": len(clean_text),
                "word_count": len(clean_text.split()),
                "section_count": len(sections),
                "internal_link_count": len(internal_links),
                "external_link_count": len(external_links)
            }
        )
