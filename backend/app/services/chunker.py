import json
import re
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

    def chunk_document(
        self,
        document_id: int,
        document_title: str,
        document_version: str,
        effective_year: Optional[int],
        pages: List[ParsedPage]
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

                # If it is a table or short section, keep it intact
                if is_table or self._approx_tokens(content) <= self.target_chunk_size:
                    chunk_text = f"[{heading}]\n{content}" if heading != "General" else content
                    meta = {
                        "document_id": document_id,
                        "document_title": document_title,
                        "document_version": document_version,
                        "page_number": page.page_number,
                        "section": heading,
                        "year": effective_year,
                        "is_table": is_table
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
                else:
                    # Paragraph / Sentence-based splitting for long sections
                    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
                    if not paragraphs:
                        paragraphs = re.split(r'(?<=[.?!])\s+', content)

                    current_piece = []
                    current_tokens = 0

                    for p in paragraphs:
                        p_tokens = self._approx_tokens(p)
                        if current_tokens + p_tokens > self.target_chunk_size and current_piece:
                            full_piece_text = " ".join(current_piece)
                            chunk_text = f"[{heading}]\n{full_piece_text}" if heading != "General" else full_piece_text
                            meta = {
                                "document_id": document_id,
                                "document_title": document_title,
                                "document_version": document_version,
                                "page_number": page.page_number,
                                "section": heading,
                                "year": effective_year,
                                "is_table": False
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
                            current_piece = [p]
                            current_tokens = p_tokens
                        else:
                            current_piece.append(p)
                            current_tokens += p_tokens

                    if current_piece:
                        full_piece_text = " ".join(current_piece)
                        chunk_text = f"[{heading}]\n{full_piece_text}" if heading != "General" else full_piece_text
                        meta = {
                            "document_id": document_id,
                            "document_title": document_title,
                            "document_version": document_version,
                            "page_number": page.page_number,
                            "section": heading,
                            "year": effective_year,
                            "is_table": False
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
