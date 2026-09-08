import logging
from typing import List
import numpy as np
from app.config import settings

logger = logging.getLogger("docusense.embeddings")

class EmbeddingService:
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self.dim = self._model.get_embedding_dimension()
            else:
                self.dim = self._model.get_sentence_embedding_dimension()
        except Exception as e:
            logger.warning(f"SentenceTransformer load failed ({e}). Using deterministic embedding fallback.")
            self._model = None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute dense vector embeddings for a list of text strings."""
        if not texts:
            return []
        
        if self._model is None:
            self._load_model()
            
        if self._model is not None:
            try:
                embeddings = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Error during encoding: {e}. Falling back to deterministic fallback.")

        # Deterministic fallback embedding for testing / fallback environments
        fallback_embeddings = []
        for text in texts:
            np.random.seed(abs(hash(text)) % (2**32))
            vec = np.random.randn(self.dim)
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            fallback_embeddings.append(vec.tolist())
        return fallback_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Compute embedding for a single user search query."""
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * self.dim

embedding_service = EmbeddingService()
