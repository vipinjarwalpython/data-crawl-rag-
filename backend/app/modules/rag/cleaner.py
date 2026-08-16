import re
from typing import List, Dict, Any, Optional
from app.core.logging import get_module_logger

logger = get_module_logger(__name__)


class TextCleaner:
    """Professional grade text cleaning engine for web crawled data.

    Removes boilerplate text, cookie banners, navigation links, tracking snippets,
    excessive whitespace, while strictly preserving document headings, structure,
    entities, contact information, and data consistency.
    """

    # Common boilerplate / noise regex patterns
    BOILERPLATE_PATTERNS = [
        r"(?i)warning!.*?(demo website|web scraping purposes|randomly assigned).*?meaning\.?",
        r"(?i)books to scrape\s+we love being scraped!?",
        r"(?i)cookie policy.*?(accept|agree|reject|settings|manage)",
        r"(?i)we use cookies to enhance your experience.*?(accept|decline|agree)",
        r"(?i)this website uses cookies.*?(accept|agree|continue)",
        r"(?i)all rights reserved\.",
        r"(?i)copyright \d{4}.*?\.?",
        r"(?i)subscribe to our newsletter.*",
        r"(?i)skip to main content",
        r"(?i)sign up for free.*",
    ]

    @staticmethod
    def clean_inline_whitespace(text: str) -> str:
        """Normalize inline whitespace while preserving characters."""
        if not text:
            return ""
        # Replace non-breaking spaces and collapse all multi-whitespace (including newlines) into single space
        cleaned = text.replace("\u00a0", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @classmethod
    def clean_text(cls, raw_text: str, remove_boilerplate: bool = True, min_paragraph_length: int = 20) -> str:
        """Clean raw text extracted from web pages without dropping headings or critical data."""
        if not raw_text:
            return ""

        text = raw_text

        if remove_boilerplate:
            for pattern in cls.BOILERPLATE_PATTERNS:
                text = re.sub(pattern, " ", text)

        # Normalize line breaks and spaces
        lines = text.splitlines()
        cleaned_lines = []

        for line in lines:
            line_str = cls.clean_inline_whitespace(line)
            if not line_str:
                continue

            # Strip pure decorative noise or symbols (e.g. "---", "===", "***", "|||", ">>>")
            if re.fullmatch(r"[-=_*~#|>\.\s]+", line_str) and not line_str.startswith("#"):
                continue

            # Check if line has alphanumeric or meaningful content
            has_alnum = any(char.isalnum() for char in line_str)
            if not has_alnum:
                continue

            # If min_paragraph_length is applied, don't drop lines that look like headings, markdown headers,
            # bullet points, entity names, phone numbers, emails, addresses, prices, or key data.
            is_heading = (
                line_str.startswith(("#", "-", "*", "•", "📍", "📞", "✉", "£", "$", "€", "₹")) or
                line_str.endswith((".", ":", "?", "!")) or
                any(char.isdigit() for char in line_str) or
                "@" in line_str or "+" in line_str or
                # Short titled lines / capitalized entity names (e.g., "Biography", "Books to Scrape")
                (len(line_str.split()) <= 6 and line_str[0].isupper())
            )

            if min_paragraph_length > 0 and len(line_str) < min_paragraph_length and not is_heading:
                # Still check if it contains actual words
                words = re.findall(r"\w+", line_str)
                if not words:
                    continue

            cleaned_lines.append(line_str)

        final_text = "\n".join(cleaned_lines)

        # Collapse 3 or more consecutive newlines into 2
        final_text = re.sub(r"\n{3,}", "\n\n", final_text)
        return final_text.strip()

    @classmethod
    def clean_heading(cls, heading: str) -> str:
        """Clean a section heading while preserving 100% of the heading text."""
        if not heading:
            return ""
        # Remove unwanted scripts or boilerplate from heading
        h = cls.clean_inline_whitespace(heading)
        # Strip leading markdown symbols if any were accidentally repeated
        h = re.sub(r"^#+\s*", "", h).strip()
        return h

    @classmethod
    def clean_document_dict(
        cls,
        doc_data: Dict[str, Any],
        remove_boilerplate: bool = True,
        min_paragraph_length: int = 20
    ) -> Dict[str, Any]:
        """Clean structured document dict while preserving headings, section hierarchy, and data consistency."""
        # 1. Clean Title & Description
        if "title" in doc_data and doc_data["title"]:
            doc_data["title"] = cls.clean_inline_whitespace(doc_data["title"])

        if "description" in doc_data and doc_data["description"]:
            doc_data["description"] = cls.clean_inline_whitespace(doc_data["description"])

        # 2. Clean structured sections preserving heading, level, and content
        cleaned_sections = []
        section_text_blocks = []

        for section in doc_data.get("sections", []):
            # Support both 'heading' and 'title' key from incoming data
            raw_heading = section.get("heading") if section.get("heading") is not None else section.get("title", "")
            raw_level = section.get("level", 1)
            raw_content = section.get("content", "")

            sec_heading = cls.clean_heading(raw_heading)
            sec_content = cls.clean_text(raw_content, remove_boilerplate=remove_boilerplate, min_paragraph_length=min_paragraph_length)

            # Preserve section if either heading or content exists
            if sec_heading or sec_content:
                cleaned_section = {
                    "heading": sec_heading,
                    "level": raw_level,
                    "content": sec_content,
                    "title": sec_heading  # For backward compatibility
                }
                cleaned_sections.append(cleaned_section)

                # Format section text with markdown header for semantic chunking & RAG
                header_prefix = "#" * max(1, min(raw_level, 6))
                if sec_heading and sec_content:
                    section_text_blocks.append(f"{header_prefix} {sec_heading}\n{sec_content}")
                elif sec_heading:
                    section_text_blocks.append(f"{header_prefix} {sec_heading}")
                elif sec_content:
                    section_text_blocks.append(sec_content)

        # 3. Clean full text
        raw_clean = doc_data.get("clean_text", "")
        cleaned_clean_text = cls.clean_text(raw_clean, remove_boilerplate=remove_boilerplate, min_paragraph_length=min_paragraph_length)

        # 4. Generate structured processed_text incorporating sections & headings
        if section_text_blocks:
            # Build processed text hierarchically from cleaned sections
            processed_clean_text = "\n\n".join(section_text_blocks)
        else:
            processed_clean_text = cleaned_clean_text

        doc_data["processed_text"] = processed_clean_text
        doc_data["sections"] = cleaned_sections
        return doc_data

