import re
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
        """Call Google Gemini API with automatic candidate model fallback."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")

        candidate_models = [
            settings.LLM_MODEL_NAME,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
        seen = set()
        models = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

        last_error = None
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
            }
            try:
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        logger.warning(f"Gemini model {model} returned status {resp.status_code}: {resp.text[:120]}")
                        last_error = f"Status {resp.status_code}: {resp.text[:120]}"
            except Exception as e:
                logger.warning(f"Gemini model {model} call failed: {e}")
                last_error = str(e)

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured.")
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are DocuSense, an advanced document intelligence assistant with dual capabilities: answering from uploaded document evidence or answering general questions using your general knowledge."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _generate_grounded_response(
        self,
        query: str,
        context_chunks: List[RetrievedCandidate],
        answer_only_from_documents: bool = True,
    ) -> Tuple[str, str]:
        """Synthesize answer with LLM using dynamic brain reasoning.

        The model evaluates whether the user is asking a general/conversational question
        or seeking information from the indexed document repository.
        Returns (answer_text, mode) where mode is 'GENERAL' or 'DOCUMENT'.
        """
        formatted_context = ""
        for idx, c in enumerate(context_chunks, 1):
            formatted_context += (
                f"\n--- SOURCE [{idx}] ---\n"
                f"Document: {c.document_name}\n"
                f"Page: {c.page_number} | Section: {c.section_heading}\n"
                f"Content:\n{c.text}\n"
            )

        doc_clause = (
            "If the question seeks company/policy facts and the provided excerpts do not contain sufficient evidence, state clearly: "
            "'The provided documents do not contain sufficient evidence to answer this question.'"
            if answer_only_from_documents
            else "If the question seeks policy facts but excerpts lack them, clearly state what is missing and offer helpful general guidance."
        )

        prompt = f"""You are DocuSense, an intelligent enterprise document assistant powered by Google Gemini.
You have two operational modes:
1. [MODE: GENERAL] - For greetings ('Hi', 'Hello', 'Good morning', 'How are you?'), chit-chat, identity queries ('Who are you?'), or generalized questions (e.g. machine learning, programming, math, science, general business advice, writing) that do NOT require specific internal company policy documents.
2. [MODE: DOCUMENT] - For questions asking about company policies, rules, working hours, remote work / WFH, leave/vacation entitlement, benefits, health reimbursement, policy IDs (e.g. HR-2024-001, HR-2026-017), versions, effective dates, or facts from uploaded corporate documents.

TASK:
Examine the user's question. Use your brain to decide whether to answer using your GENERAL brain or your DOCUMENT retrieval brain.

FORMAT:
On the very first line, write:
[MODE: GENERAL] or [MODE: DOCUMENT]
Then provide your complete, well-crafted answer.

RULES FOR [MODE: GENERAL]:
- Answer warmly, helpfully, and clearly using your general intelligence.
- NEVER claim 'The provided documents do not contain sufficient evidence' for greetings or general questions!
- Courteously mention that you are also ready to search and answer questions about their uploaded company documents and policies.

RULES FOR [MODE: DOCUMENT]:
- Answer accurately and thoroughly using the provided Context Excerpts.
- Explicitly cite the document name, policy version/year, page number, and section heading.
- If multiple versions (e.g. 2024 vs 2026) are present, contrast differences clearly.
- {doc_clause}

Context Excerpts:
{formatted_context if formatted_context else "No relevant document excerpts were retrieved."}

User Question:
{query}

Response:"""

        raw_answer = ""
        try:
            if settings.GEMINI_API_KEY:
                raw_answer = self._call_gemini(prompt)
            elif settings.OPENAI_API_KEY:
                raw_answer = self._call_openai(prompt)
        except Exception as e:
            logger.warning(f"LLM API call failed ({e}). Using offline grounded synthesis fallback.")

        if raw_answer:
            cleaned = raw_answer.strip()
            mode = "DOCUMENT"
            mode_match = re.search(r"^\s*\[?MODE\s*:\s*(GENERAL|DOCUMENT)\]?:?", cleaned, re.IGNORECASE)
            if mode_match:
                mode = mode_match.group(1).upper()
                cleaned = cleaned[mode_match.end():].strip()
            elif "MODE: GENERAL" in cleaned[:40] or "MODE:GENERAL" in cleaned[:40]:
                mode = "GENERAL"
                lines = cleaned.split("\n", 1)
                cleaned = lines[1].strip() if len(lines) > 1 else lines[0]
            elif "MODE: DOCUMENT" in cleaned[:40] or "MODE:DOCUMENT" in cleaned[:40]:
                mode = "DOCUMENT"
                lines = cleaned.split("\n", 1)
                cleaned = lines[1].strip() if len(lines) > 1 else lines[0]
            else:
                if temporal_analyzer.is_conversational_or_greeting(query):
                    mode = "GENERAL"
                else:
                    mode = "DOCUMENT"

            return cleaned, mode

        # Offline fallback when LLM is unavailable
        if temporal_analyzer.is_conversational_or_greeting(query):
            return (
                "Hello! I am DocuSense, your document intelligence assistant powered by Gemini. "
                "I can answer general questions using my general reasoning brain, as well as help you search, compare, "
                "and verify claims across your uploaded company policies and documents.",
                "GENERAL"
            )

        if not context_chunks:
            return (
                (
                    "The provided documents do not contain sufficient evidence to answer this question."
                    if answer_only_from_documents
                    else "No relevant document evidence was found to answer this question."
                ),
                "DOCUMENT"
            )

        top_excerpts = [f"- {c.text[:220]}... *(Source: {c.document_name}, Page {c.page_number})*" for c in context_chunks[:3]]
        return (
            f"Based on the retrieved document evidence:\n\n"
            + "\n\n".join(top_excerpts)
            + "\n\n*(Evidence grounded directly from verified document pages)*",
            "DOCUMENT"
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

        # Step 4: Intelligent LLM Generation
        t3 = time.time()
        answer, mode = self._generate_grounded_response(
            cleaned_query, top_chunks, answer_only_from_documents
        )

        if mode == "GENERAL":
            citations = []
            confidence = 0.95
            chunks_count = 0
            retrieval_expl = "Answered using Gemini general reasoning brain"
        else:
            # Document mode
            if not top_chunks or "not contain sufficient evidence" in answer.lower() or "no relevant document evidence" in answer.lower():
                citations = []
                confidence = 0.4 if top_chunks else 0.0
                chunks_count = len(top_chunks)
                retrieval_expl = "Searched repository; no sufficient document evidence found"
            else:
                chunks_count = len(top_chunks)
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
                retrieval_expl = (
                    f"Retrieved with {'hybrid dense + BM25' if use_hybrid else 'dense semantic'} search"
                    + (f", filtered to year {target_year}" if target_year else "")
                    + (f", filtered to versions {', '.join(versions)}" if versions else "")
                    + (", answer grounded in indexed documents" if answer_only_from_documents else "")
                )

        latencies["generation_ms"] = round((time.time() - t3) * 1000, 2)
        latencies["total_ms"] = round((time.time() - t0) * 1000, 2)

        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            confidence_score=confidence,
            citations=citations,
            latency_ms=latencies,
            retrieved_chunks_count=chunks_count,
            rewritten_query=rewritten_query if rewritten_query != cleaned_query else None,
            retrieval_explanation=retrieval_expl,
        )

rag_engine = RAGEngine()
