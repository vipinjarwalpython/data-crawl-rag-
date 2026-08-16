import json
import os
from pathlib import Path
from typing import List, Optional, Tuple
import aiofiles
from app.core.config import settings
from app.core.logging import get_module_logger
from app.modules.scraping.schemas import ScrapedDocument, ScrapedDocumentSummary

logger = get_module_logger(__name__)


class JSONStore:
    """Production JSON Storage Manager for scraped web documents."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.storage_dir = storage_dir or settings.resolve_path(settings.SCRAPED_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, doc_id: str) -> Path:
        """Get file path for a given doc_id."""
        clean_id = doc_id.replace(".json", "")
        return self.storage_dir / f"{clean_id}.json"

    async def save_document(self, doc: ScrapedDocument) -> Tuple[ScrapedDocument, bool]:
        """Save a ScrapedDocument to a JSON file.

        Returns (document, is_new_or_updated: bool)
        """
        file_path = self._get_file_path(doc.id)
        
        # Check if identical document already exists
        if file_path.exists():
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    existing_data = json.loads(content)
                    if existing_data.get("content_hash") == doc.content_hash:
                        logger.debug(f"Document {doc.id} ({doc.url}) unchanged. Skipping rewrite.")
                        return doc, False
            except Exception as e:
                logger.warning(f"Error checking existing document {doc.id}: {e}")

        # Write formatted JSON to disk
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(doc.model_dump_json(indent=2))

        logger.info(f"Saved document to {file_path.name} (Title: {doc.title[:40]})")
        return doc, True

    async def get_document(self, doc_id: str) -> Optional[ScrapedDocument]:
        """Retrieve a full ScrapedDocument by doc_id."""
        file_path = self._get_file_path(doc_id)
        if not file_path.exists():
            return None

        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                return ScrapedDocument(**data)
        except Exception as e:
            logger.error(f"Failed to load document {doc_id}: {e}")
            return None

    async def document_exists(self, doc_id: str) -> bool:
        """Check if document JSON file exists."""
        return self._get_file_path(doc_id).exists()

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        query: Optional[str] = None
    ) -> Tuple[List[ScrapedDocumentSummary], int]:
        """List summaries of all stored documents with pagination and optional search."""
        summaries: List[ScrapedDocumentSummary] = []
        json_files = list(self.storage_dir.glob("*.json"))

        for file_path in json_files:
            try:
                # Read basic metadata
                stat = file_path.stat()
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)

                title = data.get("title", "Untitled")
                url = data.get("url", "")
                
                # Optional query filter
                if query:
                    q_lower = query.lower()
                    if q_lower not in title.lower() and q_lower not in url.lower():
                        continue

                clean_text = data.get("clean_text", "")
                sections = data.get("sections", [])

                summaries.append(ScrapedDocumentSummary(
                    id=data.get("id", file_path.stem),
                    url=url,
                    title=title,
                    content_hash=data.get("content_hash", ""),
                    scraped_at=data.get("scraped_at", ""),
                    file_name=file_path.name,
                    file_size_bytes=stat.st_size,
                    total_sections=len(sections),
                    total_characters=len(clean_text)
                ))
            except Exception as e:
                logger.warning(f"Error parsing file {file_path}: {e}")
                continue

        # Sort by scraped_at descending (newest first)
        summaries.sort(key=lambda x: x.scraped_at, reverse=True)
        total_count = len(summaries)
        paginated = summaries[skip : skip + limit]

        return paginated, total_count

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document JSON file by doc_id."""
        file_path = self._get_file_path(doc_id)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted document {file_path.name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete {file_path.name}: {e}")
                return False
        return False


json_store = JSONStore()
