import logging
from typing import List, Dict, Any, Tuple
from sqlmodel import Session, select
from app.models.document import Document, Chunk, ClauseComparison, CompareResponse
from app.database.db import engine

logger = logging.getLogger("docusense.comparison")

class DocumentComparator:
    @staticmethod
    def compare_documents(doc_a_id: int, doc_b_id: int) -> CompareResponse:
        """Compare two document versions, align sections, and detect clause additions/modifications/deletions."""
        with Session(engine) as session:
            doc_a = session.get(Document, doc_a_id)
            doc_b = session.get(Document, doc_b_id)

            if not doc_a or not doc_b:
                raise ValueError("One or both documents not found.")

            chunks_a = session.exec(select(Chunk).where(Chunk.document_id == doc_a_id)).all()
            chunks_b = session.exec(select(Chunk).where(Chunk.document_id == doc_b_id)).all()

            # Group chunks by section heading
            sections_a = {}
            for c in chunks_a:
                heading = c.section_heading or "General"
                if heading not in sections_a:
                    sections_a[heading] = []
                sections_a[heading].append(c)

            sections_b = {}
            for c in chunks_b:
                heading = c.section_heading or "General"
                if heading not in sections_b:
                    sections_b[heading] = []
                sections_b[heading].append(c)

            matrix: List[ClauseComparison] = []
            all_headings = set(list(sections_a.keys()) + list(sections_b.keys()))

            for heading in sorted(all_headings):
                list_a = sections_a.get(heading, [])
                list_b = sections_b.get(heading, [])

                text_a = " ".join([c.text for c in list_a]).strip() if list_a else None
                text_b = " ".join([c.text for c in list_b]).strip() if list_b else None
                page_a = list_a[0].page_number if list_a else None
                page_b = list_b[0].page_number if list_b else None

                if text_a and not text_b:
                    change_type = "removed"
                    summary = f"Clause removed in {doc_b.title or doc_b.filename}."
                elif not text_a and text_b:
                    change_type = "added"
                    summary = f"New clause introduced in {doc_b.title or doc_b.filename}."
                elif text_a == text_b:
                    change_type = "unchanged"
                    summary = "Clause text is identical across both versions."
                else:
                    change_type = "modified"
                    summary = "Clause policy/wording has been updated or amended."

                matrix.append(ClauseComparison(
                    topic=heading,
                    doc_a_section=heading if text_a else None,
                    doc_a_text=text_a[:350] + ("..." if text_a and len(text_a) > 350 else "") if text_a else None,
                    doc_a_page=page_a,
                    doc_b_section=heading if text_b else None,
                    doc_b_text=text_b[:350] + ("..." if text_b and len(text_b) > 350 else "") if text_b else None,
                    doc_b_page=page_b,
                    change_type=change_type,
                    summary_of_change=summary
                ))

            return CompareResponse(
                doc_a_title=doc_a.title or doc_a.filename,
                doc_b_title=doc_b.title or doc_b.filename,
                comparison_matrix=matrix,
                contradictions_detected=[]
            )

document_comparator = DocumentComparator()
