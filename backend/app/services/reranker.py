import logging
import threading
from typing import List
from app.config import settings
from app.services.retrieval import RetrievedCandidate

logger = logging.getLogger("docusense.reranker")

class ReRankerService:
    def __init__(self):
        self.model_name = settings.RERANKER_MODEL
        self._model = None
        self._state = "not_started"
        self._error = None
        self._load_event = threading.Event()
        self._load_lock = threading.Lock()
        self._load_thread = None

    def _load_model_once(self):
        with self._load_lock:
            if self._state in {"loading", "ready", "failed"}:
                return
            self._state = "loading"

        if settings.MODEL_RUNTIME_MODE == "deterministic":
            self._state = "ready"
            self._load_event.set()
            logger.info("Reranker ready in deterministic development mode")
            return

        try:
            from sentence_transformers import CrossEncoder
            logger.info("Loading Cross-Encoder re-ranker: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
            self._state = "ready"
            logger.info("Reranker model ready: %s", self.model_name)
        except Exception as exc:
            self._error = str(exc)
            self._state = "failed"
            logger.exception("Reranker load failed; fusion scores remain available")
        finally:
            self._load_event.set()

    def start_loading(self) -> None:
        with self._load_lock:
            if self._state in {"loading", "ready", "failed"}:
                return
            self._load_thread = threading.Thread(
                target=self._load_model_once,
                name="docusense-reranker-loader",
                daemon=True,
            )
            self._load_thread.start()

    def ensure_ready(self) -> None:
        self.start_loading()
        self._load_event.wait(timeout=settings.MODEL_LOAD_TIMEOUT_SECONDS)

    def status(self) -> dict:
        return {
            "status": "ok" if self._state == "ready" else self._state,
            "mode": settings.MODEL_RUNTIME_MODE,
            "model": self.model_name,
            "loaded": self._model is not None or settings.MODEL_RUNTIME_MODE == "deterministic",
            "error": self._error,
        }

    def rerank(self, query: str, candidates: List[RetrievedCandidate], top_k: int = 5) -> List[RetrievedCandidate]:
        """Score (query, chunk_text) pairs using cross-encoder and return top_k."""
        if not candidates:
            return []

        self.ensure_ready()

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
