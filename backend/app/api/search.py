from typing import List
from fastapi import APIRouter
from app.models.document import SearchQuery, SearchResultItem
from app.services.retrieval import hybrid_retriever

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("", response_model=List[SearchResultItem])
def search_documents(payload: SearchQuery):
    """Diagnostic search endpoint supporting Dense, Sparse BM25, or Hybrid (RRF)."""
    if payload.mode == "dense":
        results = hybrid_retriever.search_dense(
            query=payload.query,
            limit=payload.top_k,
            document_ids=payload.document_ids,
            year=payload.year,
            versions=payload.versions
        )
        return [
            SearchResultItem(
                chunk_id=0,
                document_id=r["document_id"],
                document_name=r["document_name"],
                page_number=r["page_number"],
                section_heading=r["section_heading"],
                text=r["text"],
                score=r["score"],
                retrieval_source="dense",
                document_version=r.get("document_version"),
                effective_from=r.get("effective_from"),
                effective_until=r.get("effective_until"),
                retrieval_explanation="Matched dense semantic retrieval"
            )
            for r in results
        ]
    elif payload.mode == "sparse":
        results = hybrid_retriever.search_sparse_bm25(
            query=payload.query,
            limit=payload.top_k,
            document_ids=payload.document_ids,
            year=payload.year,
            versions=payload.versions
        )
        return [
            SearchResultItem(
                chunk_id=r.get("chunk_id", 0),
                document_id=r["document_id"],
                document_name=r["document_name"],
                page_number=r["page_number"],
                section_heading=r["section_heading"],
                text=r["text"],
                score=r["score"],
                retrieval_source="sparse_bm25",
                document_version=r.get("document_version"),
                effective_from=r.get("effective_from"),
                effective_until=r.get("effective_until"),
                retrieval_explanation="Matched BM25 keyword retrieval"
            )
            for r in results
        ]
    else:  # Hybrid
        candidates = hybrid_retriever.hybrid_search(
            query=payload.query,
            limit=payload.top_k,
            document_ids=payload.document_ids,
            year=payload.year,
            versions=payload.versions
        )
        return [
            SearchResultItem(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_name=c.document_name,
                page_number=c.page_number,
                section_heading=c.section_heading,
                text=c.text,
                score=c.score,
                retrieval_source=c.source,
                document_version=c.document_version,
                effective_from=c.effective_from,
                effective_until=c.effective_until,
                retrieval_explanation=c.retrieval_explanation
            )
            for c in candidates
        ]
