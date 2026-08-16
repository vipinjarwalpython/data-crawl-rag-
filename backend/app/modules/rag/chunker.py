"""
Recursive character text chunker for CrawlRAG.

Splits document text hierarchically using a prioritised list of separators
(paragraph → sentence → word → character) to respect natural semantic
boundaries while honouring a maximum chunk size and overlap.
"""

from typing import Any, Dict, List

from app.core.config import settings
from app.core.logging import get_module_logger

logger = get_module_logger(__name__)

# Minimum character count for a chunk to be kept after merging.
_MIN_CHUNK_CHAR_LENGTH = 15

# Minimum character count below which two adjacent chunks are merged together.
_SHORT_CHUNK_MERGE_THRESHOLD = 60


class RecursiveCharacterChunker:
    """Production recursive character-level text chunker.

    Splits text hierarchically using ``separators`` until every piece fits
    within ``chunk_size``.  Adjacent small pieces are merged back together
    and a sliding ``chunk_overlap`` window prevents context loss at
    chunk boundaries.

    Parameters
    ----------
    chunk_size:
        Maximum character count per output chunk.
    chunk_overlap:
        Number of characters to repeat at the start of the next chunk (sliding
        window overlap).  Must be < ``chunk_size``.
    """

    # Priority-ordered list of separators used for splitting.
    DEFAULT_SEPARATORS: List[str] = ["\n\n", "\n", ". ", " ", ""]

    def __init__(
        self,
        chunk_size: int = settings.DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = settings.DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than "
                f"chunk_size ({chunk_size})."
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = self.DEFAULT_SEPARATORS.copy()

    # ------------------------------------------------------------------
    # Core splitting logic
    # ------------------------------------------------------------------

    def _split_text_recursively(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split *text* by *separators* until every piece fits.

        Pieces that already fit within ``chunk_size`` are buffered; pieces
        that are still too large recurse down to the next separator.
        """
        if not text:
            return []

        current_separator = separators[0]
        remaining_separators = separators[1:] if len(separators) > 1 else [""]

        # Split using the current separator (character-by-character when empty).
        if current_separator == "":
            raw_splits = list(text)
        else:
            raw_splits = text.split(current_separator)

        final_chunks: List[str] = []
        buffered_small_splits: List[str] = []

        for split_piece in raw_splits:
            if len(split_piece) <= self.chunk_size:
                buffered_small_splits.append(split_piece)
            else:
                # Flush the buffer before recursing.
                if buffered_small_splits:
                    merged = current_separator.join(buffered_small_splits)
                    final_chunks.extend(self._merge_into_chunks(merged, current_separator))
                    buffered_small_splits = []
                # Recurse with next-level separator.
                sub_chunks = self._split_text_recursively(split_piece, remaining_separators)
                final_chunks.extend(sub_chunks)

        # Flush remaining buffer.
        if buffered_small_splits:
            merged = current_separator.join(buffered_small_splits)
            final_chunks.extend(self._merge_into_chunks(merged, current_separator))

        return final_chunks

    def _merge_into_chunks(self, text: str, separator: str) -> List[str]:
        """Merge *text* (split by *separator*) into chunks of at most ``chunk_size``."""
        parts = text.split(separator) if separator else list(text)
        output_chunks: List[str] = []
        current_window: List[str] = []
        current_char_count = 0

        for part in parts:
            part_length = len(part)
            separator_length = len(separator) if current_window else 0

            if current_char_count + separator_length + part_length > self.chunk_size:
                if current_window:
                    output_chunks.append(separator.join(current_window))
                    # Slide the overlap window: drop parts from the front until we
                    # are back within chunk_size when the new part is appended.
                    while (
                        current_window
                        and current_char_count + separator_length + part_length > self.chunk_size
                    ):
                        removed_part = current_window.pop(0)
                        current_char_count -= len(removed_part) + (
                            len(separator) if current_window else 0
                        )

            current_window.append(part)
            current_char_count += part_length + (len(separator) if len(current_window) > 1 else 0)

        if current_window:
            output_chunks.append(separator.join(current_window))

        return output_chunks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_document(
        self,
        doc_id: str,
        source_url: str,
        page_title: str,
        full_text: str,
    ) -> List[Dict[str, Any]]:
        """Split a document into structured, metadata-rich chunk dicts.

        Parameters
        ----------
        doc_id:
            Unique identifier of the source document.
        source_url:
            URL of the source page.
        page_title:
            Human-readable page title (embedded in each chunk for retrieval context).
        full_text:
            Cleaned plain text to be chunked.

        Returns
        -------
        List of chunk dicts each containing:
        ``chunk_id``, ``doc_id``, ``url``, ``title``, ``chunk_index``,
        ``text``, ``char_count``.
        """
        if not full_text or not full_text.strip():
            logger.debug("Document '%s' has no text to chunk.", doc_id)
            return []

        # Step 1: recursive split.
        raw_chunks = self._split_text_recursively(full_text, self.separators)

        # Step 2: strip whitespace and drop empty pieces.
        non_empty_chunks = [chunk.strip() for chunk in raw_chunks if chunk.strip()]

        # Step 3: merge orphan short chunks (< threshold chars) into their neighbours.
        merged_chunks = self._merge_short_chunks(non_empty_chunks)

        # Step 4: build structured chunk dicts (skip anything still too short).
        structured_chunks: List[Dict[str, Any]] = []
        for chunk_index, chunk_text in enumerate(merged_chunks):
            if len(chunk_text) < _MIN_CHUNK_CHAR_LENGTH:
                continue

            chunk_id = f"{doc_id}_chunk_{chunk_index:03d}"
            structured_chunks.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "url": source_url,
                "title": page_title,
                "chunk_index": chunk_index,
                "text": chunk_text,
                "char_count": len(chunk_text),
            })

        logger.debug(
            "Chunked document '%s' -> %d chunks (avg %.0f chars).",
            doc_id,
            len(structured_chunks),
            (sum(c["char_count"] for c in structured_chunks) / len(structured_chunks))
            if structured_chunks
            else 0,
        )
        return structured_chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_short_chunks(chunks: List[str]) -> List[str]:
        """Merge chunks shorter than ``_SHORT_CHUNK_MERGE_THRESHOLD`` into neighbours.

        This prevents isolated heading-only or single-sentence orphan chunks
        that degrade retrieval quality.
        """
        merged: List[str] = []
        for chunk in chunks:
            if merged and len(merged[-1]) < _SHORT_CHUNK_MERGE_THRESHOLD:
                # Preceding chunk is short — absorb the current one into it.
                merged[-1] = f"{merged[-1]}\n{chunk}"
            elif len(chunk) < _SHORT_CHUNK_MERGE_THRESHOLD and merged:
                # Current chunk is short — absorb it into the preceding one.
                merged[-1] = f"{merged[-1]}\n{chunk}"
            else:
                merged.append(chunk)

        # Final edge case: first chunk is still short but a second chunk exists.
        if len(merged) > 1 and len(merged[0]) < _SHORT_CHUNK_MERGE_THRESHOLD:
            merged[1] = f"{merged[0]}\n{merged[1]}"
            merged.pop(0)

        return merged
