import json
import re
import datetime
from typing import List, Dict, Any, Optional
from app.services.parser import ParsedPage

class StructuredChunk:
    def __init__(
        self,
        document_id: int,
        page_number: int,
        chunk_index: int,
        section_heading: str,
        text: str,
        token_count: int,
        metadata: Dict[str, Any]
    ):
        self.document_id = document_id
        self.page_number = page_number
        self.chunk_index = chunk_index
        self.section_heading = section_heading
        self.text = text
        self.token_count = token_count
        self.metadata = metadata

class StructureAwareChunker:
    def __init__(self, target_chunk_size: int = 350, chunk_overlap: int = 50):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def _approx_tokens(self, text: str) -> int:
        return len(text.split())

    def _split_text(self, content: str, is_table: bool) -> List[str]:
        if is_table:
            rows = [row.strip() for row in content.splitlines() if row.strip()]
            pieces: List[str] = []
            current: List[str] = []
            current_tokens = 0
            for row in rows:
                row_tokens = self._approx_tokens(row)
                if current and current_tokens + row_tokens > self.target_chunk_size:
                    pieces.append("\n".join(current))
                    current = []
                    current_tokens = 0
                current.append(row)
                current_tokens += row_tokens
            if current:
                pieces.append("\n".join(current))
            return pieces

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", content.replace("\n", " ")) if part.strip()]
        if not sentences:
            return [content.strip()]

        pieces: List[str] = []
        current: List[str] = []
        current_tokens = 0
        for sentence in sentences:
            sentence_tokens = self._approx_tokens(sentence)
            if current and current_tokens + sentence_tokens > self.target_chunk_size:
                pieces.append(" ".join(current))
                overlap = current[-1:] if self.chunk_overlap else []
                current = overlap + [sentence]
                current_tokens = sum(self._approx_tokens(item) for item in current)
            else:
                current.append(sentence)
                current_tokens += sentence_tokens
        if current:
            pieces.append(" ".join(current))
        return pieces

    def chunk_document(
        self,
        document_id: int,
        document_title: str,
        document_version: str,
        effective_from: Optional[datetime.date],
        pages: List[ParsedPage],
        effective_until: Optional[datetime.date] = None
    ) -> List[StructuredChunk]:
        """
        Produce structure-aware chunks that maintain section context,
        avoid splitting inside sentences, and embed metadata.
        """
        chunks: List[StructuredChunk] = []
        global_chunk_idx = 0

        for page in pages:
            for section in page.sections:
                heading = section.get("heading", "General")
                content = section.get("content", "").strip()
                is_table = section.get("is_table", False)

                if not content:
                    continue

                for piece in self._split_text(content, is_table):
                    chunk_text = f"[{heading}]\n{piece}" if heading != "General" else piece
                    meta = {
                        "document_id": document_id,
                        "document_title": document_title,
                        "document_version": document_version,
                        "version": document_version,
                        "page_number": page.page_number,
                        "source_page": page.page_number,
                        "section": heading,
                        "section_heading": heading,
                        "effective_from": effective_from.isoformat() if effective_from else None,
                        "effective_until": effective_until.isoformat() if effective_until else None,
                        "year": effective_from.year if effective_from else None,
                        "is_table": is_table,
                    }
                    chunks.append(StructuredChunk(
                        document_id=document_id,
                        page_number=page.page_number,
                        chunk_index=global_chunk_idx,
                        section_heading=heading,
                        text=chunk_text,
                        token_count=self._approx_tokens(chunk_text),
                        metadata=meta
                    ))
                    global_chunk_idx += 1

        return chunks

chunker = StructureAwareChunker()
