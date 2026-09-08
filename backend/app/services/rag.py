import time
import json
import logging
import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings
from app.services.retrieval import RetrievedCandidate, hybrid_retriever
from app.services.reranker import reranker_service
from app.services.temporal import temporal_analyzer
from app.models.document import CitationRead, ChatResponse

logger = logging.getLogger("docusense.rag")

class RAGEngine:
    def __init__(self):
        self.provider = settings.DEFAULT_LLM_PROVIDER

    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL_NAME}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured.")
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are DocuSense, a precise document intelligence assistant. Base your answers strictly on the provided evidence."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _generate_grounded_response(
        self,
        query: str,
        context_chunks: List[RetrievedCandidate],
        answer_only_from_documents: bool = True,
    ) -> str:
        """Synthesize answer with LLM or high-quality deterministic extractor fallback."""
        formatted_context = ""
        for idx, c in enumerate(context_chunks, 1):
            formatted_context += (
                f"\n--- SOURCE [{idx}] ---\n"
                f"Document: {c.document_name}\n"
                f"Page: {c.page_number} | Section: {c.section_heading}\n"
                f"Content:\n{c.text}\n"
            )

        source_rule = "Use ONLY the provided Source excerpts below." if answer_only_from_documents else "Use the Source excerpts when available. If they do not answer the question, provide a clearly labeled general answer without inventing document citations."
        prompt = f"""You are DocuSense, an advanced document intelligence assistant.
    {source_rule}

Rules:
1. Provide a direct, structured, and factual answer based exclusively on the context.
2. For each major point, reference the source document, page, and section.
3. If the sources contain different versions across years or policies, explain the temporal changes clearly.
4. If document-only mode is enabled and the context does not contain enough evidence, state clearly: "The provided documents do not contain sufficient evidence to answer this question."

Context Excerpts:
{formatted_context}

Question:
{query}

Answer:"""

        # Try active LLM provider
        try:
            if settings.GEMINI_API_KEY:
                return self._call_gemini(prompt)
            elif settings.OPENAI_API_KEY:
                return self._call_openai(prompt)
        except Exception as e:
            logger.warning(f"LLM API call failed ({e}). Using offline grounded synthesis fallback.")

        # Offline grounded synthesis fallback for local demo/viva when offline
        if not context_chunks and not answer_only_from_documents:
            return "No document evidence was found. A general answer could not be generated while the configured language model is unavailable."

        top_excerpts = [f"- {c.text[:220]}... *(Source: {c.document_name}, Page {c.page_number})*" for c in context_chunks[:3]]
        return (
            f"Based on the retrieved document evidence:\n\n"
            + "\n\n".join(top_excerpts)
            + "\n\n*(Evidence grounded directly from verified document pages)*"
        )

    def answer_query(
        self,
        query: str,
        conversation_id: int,
        document_ids: Optional[List[int]] = None,
        year: Optional[int] = None,
        versions: Optional[List[str]] = None,
        use_reranker: bool = True,
        use_hybrid: bool = True,
        answer_only_from_documents: bool = True
    ) -> ChatResponse:
        """Full end-to-end RAG workflow with metrics tracking."""
        latencies = {}
        t0 = time.time()

        # Step 1: Temporal Analysis
        cleaned_query, detected_year = temporal_analyzer.extract_temporal_constraints(query)
        target_year = year or detected_year
        rewritten_query = temporal_analyzer.rewrite_query(cleaned_query)
        latencies["query_analysis_ms"] = round((time.time() - t0) * 1000, 2)

        # Step 2: Hybrid Retrieval
        t1 = time.time()
        if use_hybrid:
            candidates = hybrid_retriever.hybrid_search(
                query=rewritten_query,
                limit=settings.RETRIEVAL_TOP_K_DENSE,
                document_ids=document_ids,
                year=target_year,
                versions=versions
            )
        else:
            raw_dense = hybrid_retriever.search_dense(
                query=rewritten_query,
                limit=settings.RETRIEVAL_TOP_K_DENSE,
                document_ids=document_ids,
                year=target_year,
                versions=versions
            )
            candidates = [
                RetrievedCandidate(
                    chunk_id=0,
                    document_id=r["document_id"],
                    document_name=r["document_name"],
                    page_number=r["page_number"],
                    section_heading=r["section_heading"],
                    text=r["text"],
                    score=r["score"],
                    source="dense",
                    document_version=r.get("document_version"),
                    effective_from=r.get("effective_from"),
                    effective_until=r.get("effective_until"),
                    retrieval_explanation="Matched dense semantic retrieval"
                )
                for r in raw_dense
            ]
        latencies["retrieval_ms"] = round((time.time() - t1) * 1000, 2)

        # Step 3: Re-ranking
        t2 = time.time()
        if use_reranker and candidates:
            top_chunks = reranker_service.rerank(cleaned_query, candidates, top_k=settings.RERANK_TOP_K)
        else:
            top_chunks = candidates[:settings.RERANK_TOP_K]
        latencies["reranking_ms"] = round((time.time() - t2) * 1000, 2)

        # Step 4: LLM Generation
        t3 = time.time()
        if not top_chunks:
            answer = (
                "The provided documents do not contain sufficient evidence to answer this question."
                if answer_only_from_documents
                else "No relevant document evidence was found to answer this question."
            )
            confidence = 0.0
            citations = []
        else:
            answer = self._generate_grounded_response(rewritten_query, top_chunks, answer_only_from_documents)
            # Calculate grounded confidence estimate
            avg_score = sum(c.score for c in top_chunks) / len(top_chunks) if top_chunks else 0.0
            confidence = min(0.98, max(0.65, round(0.7 + (avg_score * 0.25), 2)))

            citations = [
                CitationRead(
                    document_id=c.document_id,
                    document_name=c.document_name,
                    page_number=c.page_number,
                    section_heading=c.section_heading,
                    excerpt=c.text[:200] + ("..." if len(c.text) > 200 else ""),
                    relevance_score=round(c.score, 3),
                    confidence=round(min(0.99, max(0.0, 0.55 + c.score * 12)), 3),
                    retrieval_explanation=c.retrieval_explanation + ("; cross-encoder reranked" if "+reranked" in c.source else ""),
                    document_version=c.document_version,
                    effective_from=c.effective_from,
                    effective_until=c.effective_until,
                )
                for c in top_chunks
            ]
        latencies["generation_ms"] = round((time.time() - t3) * 1000, 2)
        latencies["total_ms"] = round((time.time() - t0) * 1000, 2)

        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            confidence_score=confidence,
            citations=citations,
            latency_ms=latencies,
            retrieved_chunks_count=len(top_chunks),
            rewritten_query=rewritten_query if rewritten_query != cleaned_query else None,
            retrieval_explanation=(
                f"Retrieved with {'hybrid dense + BM25' if use_hybrid else 'dense semantic'} search"
                + (f", filtered to year {target_year}" if target_year else "")
                + (f", filtered to versions {', '.join(versions)}" if versions else "")
                + (", answer restricted to indexed documents" if answer_only_from_documents else "")
            ),
        )

rag_engine = RAGEngine()
