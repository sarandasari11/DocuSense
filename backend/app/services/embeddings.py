import logging
import hashlib
import threading
from typing import List
import numpy as np
from app.config import settings

logger = logging.getLogger("docusense.embeddings")

class EmbeddingService:
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM
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
            logger.info("Embedding service ready in deterministic development mode")
            return

        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self.dim = self._model.get_embedding_dimension()
            else:
                self.dim = self._model.get_sentence_embedding_dimension()
            self._state = "ready"
            logger.info("Embedding model ready: %s", self.model_name)
        except Exception as exc:
            self._error = str(exc)
            self._state = "failed"
            logger.exception("Embedding model load failed; deterministic fallback remains available")
        finally:
            self._load_event.set()

    def start_loading(self) -> None:
        with self._load_lock:
            if self._state in {"loading", "ready", "failed"}:
                return
            self._load_thread = threading.Thread(
                target=self._load_model_once,
                name="docusense-embedding-loader",
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

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute dense vector embeddings for a list of text strings."""
        if not texts:
            return []
        
        self.ensure_ready()
            
        if self._model is not None:
            try:
                embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Error during encoding: {e}. Falling back to deterministic fallback.")

        # Deterministic fallback embedding for testing / fallback environments
        fallback_embeddings = []
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            vec = np.random.default_rng(seed).standard_normal(self.dim)
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            fallback_embeddings.append(vec.tolist())
        return fallback_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Compute embedding for a single user search query."""
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * self.dim

embedding_service = EmbeddingService()
