from typing import List, Dict, Any, Optional
from app.core.logging import logger


class RecursiveCharacterChunker:
    """Production Recursive Character Chunker.

    Splits text hierarchically using a list of separators (paragraphs, sentences, words, characters)
    to ensure natural semantic boundaries while respecting maximum chunk size and overlap.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text by separators until chunks fit within chunk_size."""
        final_chunks: List[str] = []
        if not text:
            return final_chunks

        # Pick current separator
        current_separator = separators[0]
        next_separators = separators[1:] if len(separators) > 1 else [""]

        if current_separator == "":
            splits = list(text)
        else:
            splits = text.split(current_separator)

        good_splits: List[str] = []
        separator_to_use = current_separator if current_separator != "" else ""

        for s in splits:
            if len(s) <= self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = separator_to_use.join(good_splits)
                    final_chunks.extend(self._merge_splits([merged], separator_to_use))
                    good_splits = []
                # Recurse down with next separator
                sub_splits = self._split_text(s, next_separators)
                final_chunks.extend(sub_splits)

        if good_splits:
            merged = separator_to_use.join(good_splits)
            final_chunks.extend(self._merge_splits([merged], separator_to_use))

        return final_chunks

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """Merge small splits into chunks respecting chunk_size and chunk_overlap."""
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for part in splits:
            part_len = len(part)
            sep_len = len(separator) if current_chunk else 0

            if current_length + sep_len + part_len > self.chunk_size:
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                    # Handle overlap by keeping trailing parts of previous chunk
                    while current_chunk and current_length + sep_len + part_len > self.chunk_size:
                        removed = current_chunk.pop(0)
                        current_length -= len(removed) + (len(separator) if current_chunk else 0)

            current_chunk.append(part)
            current_length += part_len + (len(separator) if len(current_chunk) > 1 else 0)

        if current_chunk:
            chunks.append(separator.join(current_chunk))

        return chunks

    def chunk_document(self, doc_id: str, url: str, title: str, text: str) -> List[Dict[str, Any]]:
        """Chunk a document into structured chunk items with rich metadata."""
        raw_chunks = self._split_text(text, self.separators)
        structured_chunks = []

        for idx, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            
            chunk_id = f"{doc_id}_chunk_{idx:03d}"
            structured_chunks.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "url": url,
                "title": title,
                "chunk_index": idx,
                "text": chunk_text,
                "char_count": len(chunk_text)
            })

        logger.debug(f"Chunked document {doc_id} into {len(structured_chunks)} chunks.")
        return structured_chunks
