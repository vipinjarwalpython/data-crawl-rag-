import re
from typing import List, Dict, Any, Optional
from app.core.logging import logger


class TextCleaner:
    """Professional grade text cleaning engine for web crawled data.

    Removes boilerplate text, cookie banners, navigation links, tracking snippets,
    excessive whitespace, and low-quality sentences.
    """

    @staticmethod
    def clean_text(raw_text: str, remove_boilerplate: bool = True, min_paragraph_length: int = 20) -> str:
        """Clean raw text extracted from web pages."""
        if not raw_text:
            return ""

        text = raw_text

        if remove_boilerplate:
            # Remove common cookie notices, privacy disclaimers, login prompts
            boilerplate_patterns = [
                r"(?i)cookie policy.*?(accept|agree|reject|settings)",
                r"(?i)we use cookies to enhance your experience.*?(accept|decline)",
                r"(?i)all rights reserved\.",
                r"(?i)copyright \d{4}.*?\.?",
                r"(?i)subscribe to our newsletter.*",
                r"(?i)skip to main content",
                r"(?i)sign up for free.*",
            ]
            for pattern in boilerplate_patterns:
                text = re.sub(pattern, " ", text)

        # Normalize line breaks and spaces
        lines = text.splitlines()
        cleaned_lines = []
        
        for line in lines:
            line_str = line.strip()
            # Retain lines ending with punctuation, numbers, contact info, emails, phone numbers, or metadata
            has_special = any(char.isdigit() for char in line_str) or "@" in line_str or "+" in line_str
            if len(line_str) < min_paragraph_length and not line_str.endswith((".", ":", "?", "!")) and not has_special:
                continue
            
            # Remove excessive internal whitespace
            line_str = re.sub(r"\s+", " ", line_str)
            if line_str:
                cleaned_lines.append(line_str)

        final_text = "\n".join(cleaned_lines)
        
        # Collapse multiple consecutive newlines
        final_text = re.sub(r"\n{3,}", "\n\n", final_text)
        return final_text.strip()

    @staticmethod
    def clean_document_dict(doc_data: Dict[str, Any], remove_boilerplate: bool = True, min_paragraph_length: int = 20) -> Dict[str, Any]:
        """Clean structured document dict (sections, clean_text, etc.)."""
        cleaned_sections = []
        for section in doc_data.get("sections", []):
            sec_title = TextCleaner.clean_text(section.get("title", ""), remove_boilerplate, min_paragraph_length=2)
            sec_content = TextCleaner.clean_text(section.get("content", ""), remove_boilerplate, min_paragraph_length)
            if sec_content:
                cleaned_sections.append({
                    "title": sec_title,
                    "content": sec_content
                })

        raw_clean = doc_data.get("clean_text", "")
        processed_clean_text = TextCleaner.clean_text(raw_clean, remove_boilerplate, min_paragraph_length)

        doc_data["processed_text"] = processed_clean_text
        doc_data["sections"] = cleaned_sections
        return doc_data
