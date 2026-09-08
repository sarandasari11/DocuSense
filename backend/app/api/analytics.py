from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from app.database.db import get_session
from app.models.document import Document, Chunk, DocumentPage, Message
from app.config import settings

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("")
def get_system_analytics(session: Session = Depends(get_session)):
    """Return platform statistics for dashboard and viva presentation."""
    total_docs = session.exec(select(func.count(Document.id))).one()
    total_pages = session.exec(select(func.count(DocumentPage.id))).one()
    total_chunks = session.exec(select(func.count(Chunk.id))).one()
    total_queries = session.exec(select(func.count(Message.id)).where(Message.role == "user")).one()

    return {
        "total_documents": total_docs,
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "total_queries_served": total_queries,
        "system_config": {
            "embedding_model": settings.EMBEDDING_MODEL,
            "reranker_model": settings.RERANKER_MODEL,
            "vector_dimension": settings.EMBEDDING_DIM,
            "retrieval_k_dense": settings.RETRIEVAL_TOP_K_DENSE,
            "retrieval_k_sparse": settings.RETRIEVAL_TOP_K_SPARSE,
            "rerank_top_k": settings.RERANK_TOP_K,
            "rrf_fusion_k": settings.RRF_K,
            "llm_provider": settings.DEFAULT_LLM_PROVIDER
        }
    }
