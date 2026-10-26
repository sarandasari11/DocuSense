import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings

logger = logging.getLogger("docusense.vector_db")

class VectorDBManager:
    def __init__(self):
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION
        self._init_client()

    def _get_client(self):
        if self.client is None:
            self._init_client()
        if self.client is None:
            raise RuntimeError("Qdrant client is not connected. Please verify QDRANT_URL and QDRANT_API_KEY.")
        return self.client

    def _init_client(self):
        try:
            if settings.QDRANT_URL:
                logger.info("Connecting to Qdrant at %s", settings.QDRANT_URL)
                self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
            elif settings.QDRANT_USE_LOCAL_STORAGE:
                logger.info(f"Initializing Qdrant locally at {settings.QDRANT_PATH}")
                self.client = QdrantClient(path=settings.QDRANT_PATH)
            else:
                logger.info(f"Connecting to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
                self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, api_key=settings.QDRANT_API_KEY)
            
            self._ensure_collection()
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            if settings.APP_ENV != "production":
                logger.info("Falling back to in-memory Qdrant for development.")
                self.client = QdrantClient(":memory:")
                self._ensure_collection()
            else:
                self.client = None

    def health_check(self) -> dict:
        try:
            client = self._get_client()
            client.get_collections()
            return {"status": "ok", "collection": self.collection_name}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    def _ensure_collection(self):
        try:
            client = self._get_client()
            collections = client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name} (dim={settings.EMBEDDING_DIM})")
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=models.Distance.COSINE
                    )
                )
                # Create payload index for fast filtering
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_id",
                    field_schema=models.PayloadSchemaType.INTEGER
                )
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="year",
                    field_schema=models.PayloadSchemaType.INTEGER
                )
        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")

    def upsert_chunks(self, points: List[models.PointStruct]):
        """Upsert a batch of chunk vectors with metadata payloads."""
        if not points:
            return
        client = self._get_client()
        client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        document_ids: Optional[List[int]] = None,
        year: Optional[int] = None
    ) -> List[Any]:
        """Search vector database with optional document and temporal metadata filters."""
        if document_ids == []:
            return []
        must_filters = []
        if document_ids is not None:
            must_filters.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids)
                )
            )
        if year:
            must_filters.append(
                models.FieldCondition(
                    key="year",
                    match=models.MatchValue(value=year)
                )
            )

        query_filter = models.Filter(must=must_filters) if must_filters else None
        client = self._get_client()

        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit
            )
            return response.points
        elif hasattr(client, "search"):
            return client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit
            )
        return []

    def delete_document_chunks(self, document_id: int):
        """Delete all chunk vectors for a given document."""
        client = self._get_client()
        client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id)
                        )
                    ]
                )
            )
        )

vector_db = VectorDBManager()
