import logging
from typing import List
from app.config import settings
from app.services.retrieval import RetrievedCandidate

logger = logging.getLogger("docusense.reranker")

class ReRankerService:
    def __init__(self):
        self.model_name = settings.RERANKER_MODEL
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading Cross-Encoder re-ranker: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
        except Exception as e:
            logger.warning(f"CrossEncoder load failed ({e}). Re-ranking will use fusion scores.")
            self._model = None

    def rerank(self, query: str, candidates: List[RetrievedCandidate], top_k: int = 5) -> List[RetrievedCandidate]:
        """Score (query, chunk_text) pairs using cross-encoder and return top_k."""
        if not candidates:
            return []

        if self._model is None:
            self._load_model()

        if self._model is not None:
            try:
                pairs = [[query, c.text] for c in candidates]
                scores = self._model.predict(pairs)
                
                for candidate, score in zip(candidates, scores):
                    candidate.score = float(score)
                    candidate.source += "+reranked"
                
                ranked = sorted(candidates, key=lambda x: x.score, reverse=True)
                return ranked[:top_k]
            except Exception as e:
                logger.error(f"Error during re-ranking: {e}")

        # Fallback to existing RRF scores
        return candidates[:top_k]

reranker_service = ReRankerService()
