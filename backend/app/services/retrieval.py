import re
import logging
import datetime
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from app.config import settings
from app.database.vector_db import vector_db
from app.services.embeddings import embedding_service
from app.database.db import engine
from app.models.document import Chunk, Document

logger = logging.getLogger("docusense.retrieval")

class RetrievedCandidate:
    def __init__(
        self,
        chunk_id: int,
        document_id: int,
        document_name: str,
        page_number: int,
        section_heading: str,
        text: str,
        score: float,
        source: str,
        document_version: Optional[str] = None,
        effective_from: Optional[datetime.date] = None,
        effective_until: Optional[datetime.date] = None,
        retrieval_explanation: str = ""
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_name = document_name
        self.page_number = page_number
        self.section_heading = section_heading
        self.text = text
        self.score = score
        self.source = source
        self.document_version = document_version
        self.effective_from = effective_from
        self.effective_until = effective_until
        self.retrieval_explanation = retrieval_explanation

class HybridRetriever:
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def resolve_document_ids(
        self,
        document_ids: Optional[List[int]] = None,
        year: Optional[int] = None,
        versions: Optional[List[str]] = None,
    ) -> Optional[List[int]]:
        """Resolve document-level filters before touching either retrieval index."""
        if document_ids is None and year is None and not versions:
            return None

        with Session(engine) as session:
            documents = session.exec(select(Document)).all()

        requested_ids = set(document_ids) if document_ids is not None else None
        requested_versions = set(versions or [])
        matched_ids = []
        for document in documents:
            if requested_ids is not None and document.id not in requested_ids:
                continue
            if requested_versions and (document.version or "1.0") not in requested_versions:
                continue
            if year is not None:
                if not document.effective_from:
                    continue
                starts_before = document.effective_from.year <= year
                ends_after = not document.effective_until or document.effective_until.year >= year
                if not (starts_before and ends_after):
                    continue
            matched_ids.append(document.id)
        return matched_ids

    @staticmethod
    def _date_value(value: Any) -> Optional[datetime.date]:
        if isinstance(value, datetime.date):
            return value
        if isinstance(value, str):
            try:
                return datetime.date.fromisoformat(value)
            except ValueError:
                return None
        return None

    def search_dense(
        self,
        query: str,
        limit: int = 20,
        document_ids: Optional[List[int]] = None,
        year: Optional[int] = None,
        versions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Dense semantic search via Qdrant."""
        resolved_ids = self.resolve_document_ids(document_ids, year, versions)
        if resolved_ids == []:
            return []
        query_vec = embedding_service.embed_query(query)
        qdrant_results = vector_db.search(
            query_vector=query_vec,
            limit=limit,
            document_ids=resolved_ids,
            year=None
        )
        
        results = []
        for r in qdrant_results:
            p = r.payload or {}
            results.append({
                "document_id": p.get("document_id"),
                "document_name": p.get("document_name", "Unknown Document"),
                "page_number": p.get("page_number", 1),
                "section_heading": p.get("section_heading", "General"),
                "text": p.get("text", ""),
                "score": float(r.score),
                "document_version": p.get("document_version", p.get("version")),
                "effective_from": self._date_value(p.get("effective_from")),
                "effective_until": self._date_value(p.get("effective_until")),
            })
        return results

    def search_sparse_bm25(
        self,
        query: str,
        limit: int = 20,
        document_ids: Optional[List[int]] = None,
        year: Optional[int] = None,
        versions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Sparse keyword retrieval using BM25Okapi over SQLite database chunks."""
        with Session(engine) as session:
            resolved_ids = self.resolve_document_ids(document_ids, year, versions)
            if resolved_ids == []:
                return []
            stmt = select(Chunk, Document.title, Document.filename, Document.version, Document.effective_from, Document.effective_until).join(Document, Chunk.document_id == Document.id)
            if resolved_ids is not None:
                stmt = stmt.where(Chunk.document_id.in_(resolved_ids))
            
            rows = session.exec(stmt).all()
            if not rows:
                return []

            corpus_chunks = []
            tokenized_corpus = []
            
            for chunk, doc_title, doc_filename, doc_version, effective_from, effective_until in rows:
                doc_name = doc_title or doc_filename
                corpus_chunks.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": doc_name,
                    "page_number": chunk.page_number,
                    "section_heading": chunk.section_heading,
                    "text": chunk.text,
                    "document_version": doc_version or "1.0",
                    "effective_from": effective_from,
                    "effective_until": effective_until,
                })
                tokenized_corpus.append(self._tokenize(chunk.text))

            if not corpus_chunks:
                return []

            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = self._tokenize(query)
            scores = bm25.get_scores(tokenized_query)

            # Sort top K
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:limit]
            
            results = []
            for idx in top_indices:
                if scores[idx] > 0.0:
                    item = corpus_chunks[idx].copy()
                    item["score"] = float(scores[idx])
                    results.append(item)
            return results

    def hybrid_search(
        self,
        query: str,
        limit: int = 15,
        document_ids: Optional[List[int]] = None,
        year: Optional[int] = None,
        versions: Optional[List[str]] = None,
        rrf_k: int = 60
    ) -> List[RetrievedCandidate]:
        """
        Reciprocal Rank Fusion (RRF) combining Dense and Sparse BM25 results:
        RRF_Score = 1/(k + rank_dense) + 1/(k + rank_bm25)
        """
        resolved_ids = self.resolve_document_ids(document_ids, year, versions)
        if resolved_ids == []:
            return []
        dense_results = self.search_dense(query, limit=settings.RETRIEVAL_TOP_K_DENSE, document_ids=resolved_ids)
        sparse_results = self.search_sparse_bm25(query, limit=settings.RETRIEVAL_TOP_K_SPARSE, document_ids=resolved_ids)

        fused_scores: Dict[str, Dict[str, Any]] = {}

        # Add Dense ranks
        for rank, item in enumerate(dense_results):
            key = f"{item['document_id']}_{item['page_number']}_{item['section_heading']}_{item['text'][:80]}"
            if key not in fused_scores:
                fused_scores[key] = {"item": item, "rrf_score": 0.0, "sources": [], "dense_rank": rank + 1}
            fused_scores[key]["rrf_score"] += 1.0 / (rrf_k + rank + 1)
            fused_scores[key]["sources"].append("dense")

        # Add Sparse ranks
        for rank, item in enumerate(sparse_results):
            key = f"{item['document_id']}_{item['page_number']}_{item['section_heading']}_{item['text'][:40]}"
            if key not in fused_scores:
                fused_scores[key] = {"item": item, "rrf_score": 0.0, "sources": [], "bm25_rank": rank + 1}
            fused_scores[key]["rrf_score"] += 1.0 / (rrf_k + rank + 1)
            fused_scores[key]["sources"].append("bm25")
            fused_scores[key]["bm25_rank"] = rank + 1

        # Sort by fused score
        sorted_candidates = sorted(fused_scores.values(), key=lambda x: x["rrf_score"], reverse=True)[:limit]

        final_list = []
        for candidate in sorted_candidates:
            item = candidate["item"]
            src_str = "+".join(candidate["sources"])
            explanation = f"Matched {src_str.upper()} retrieval"
            if len(candidate["sources"]) > 1:
                explanation += " with reciprocal-rank fusion"
            final_list.append(RetrievedCandidate(
                chunk_id=item.get("chunk_id", 0),
                document_id=item["document_id"],
                document_name=item["document_name"],
                page_number=item["page_number"],
                section_heading=item["section_heading"],
                text=item["text"],
                score=candidate["rrf_score"],
                source=src_str,
                document_version=item.get("document_version"),
                effective_from=item.get("effective_from"),
                effective_until=item.get("effective_until"),
                retrieval_explanation=explanation,
            ))

        return final_list

hybrid_retriever = HybridRetriever()
