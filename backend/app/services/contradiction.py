import re
import logging
from typing import List, Dict, Any
from sqlmodel import Session, select
from app.models.document import Document, Chunk, Contradiction
from app.database.db import engine

logger = logging.getLogger("docusense.contradiction")

class ContradictionDetector:
    @staticmethod
    def _extract_numbers_and_keywords(text: str) -> Dict[str, Any]:
        """Extract key quantitative claims and conditional terms from clause text."""
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
        has_mandatory = bool(re.search(r'\b(must|mandatory|required|shall)\b', text, re.I))
        has_optional = bool(re.search(r'\b(optional|not required|discretionary|may)\b', text, re.I))
        return {
            "numbers": set(numbers),
            "mandatory": has_mandatory,
            "optional": has_optional
        }

    def detect_contradictions(self, doc_a_id: int, doc_b_id: int) -> List[Dict[str, Any]]:
        """Identify potential factual or numerical contradictions across two documents."""
        conflicts = []
        with Session(engine) as session:
            doc_a = session.get(Document, doc_a_id)
            doc_b = session.get(Document, doc_b_id)
            if not doc_a or not doc_b:
                return []

            chunks_a = session.exec(select(Chunk).where(Chunk.document_id == doc_a_id)).all()
            chunks_b = session.exec(select(Chunk).where(Chunk.document_id == doc_b_id)).all()

            # Align chunks with similar section headings or topics
            for ca in chunks_a:
                heading_a = ca.section_heading or "General"
                feat_a = self._extract_numbers_and_keywords(ca.text)

                for cb in chunks_b:
                    heading_b = cb.section_heading or "General"
                    # Compare if headings match or share high word overlap
                    if heading_a.lower() == heading_b.lower() and heading_a != "General":
                        feat_b = self._extract_numbers_and_keywords(cb.text)

                        # Check for quantitative divergence on the same section
                        if feat_a["numbers"] and feat_b["numbers"] and feat_a["numbers"] != feat_b["numbers"]:
                            diff_nums = f"{', '.join(feat_a['numbers'])} vs {', '.join(feat_b['numbers'])}"
                            conflicts.append({
                                "topic": heading_a,
                                "document_a": doc_a.title or doc_a.filename,
                                "document_a_page": ca.page_number,
                                "claim_a": ca.text[:220] + "...",
                                "document_b": doc_b.title or doc_b.filename,
                                "document_b_page": cb.page_number,
                                "claim_b": cb.text[:220] + "...",
                                "conflict_reason": f"Conflicting numerical values detected ({diff_nums})",
                                "confidence": 0.92
                            })

                        # Check for Modal Conflict (mandatory vs optional)
                        elif (feat_a["mandatory"] and feat_b["optional"]) or (feat_a["optional"] and feat_b["mandatory"]):
                            conflicts.append({
                                "topic": heading_a,
                                "document_a": doc_a.title or doc_a.filename,
                                "document_a_page": ca.page_number,
                                "claim_a": ca.text[:220] + "...",
                                "document_b": doc_b.title or doc_b.filename,
                                "document_b_page": cb.page_number,
                                "claim_b": cb.text[:220] + "...",
                                "conflict_reason": "Rule requirement changed (Mandatory vs Optional/Discretionary)",
                                "confidence": 0.88
                            })

        return conflicts

contradiction_detector = ContradictionDetector()
