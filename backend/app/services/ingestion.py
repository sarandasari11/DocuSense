import os
import uuid
import json
import logging
from typing import Optional
from sqlmodel import Session, select
from qdrant_client.http import models as qmodels

from app.models.document import Document, DocumentPage, Chunk
from app.services.parser import DocumentParser
from app.services.chunker import chunker
from app.services.embeddings import embedding_service
from app.database.vector_db import vector_db
from app.database.db import engine

logger = logging.getLogger("docusense.ingestion")

class IngestionService:
    @staticmethod
    def process_document(document_id: int):
        """Full pipeline: Parse -> Extract Pages -> Smart Chunk -> Embed -> Vector DB & SQLite."""
        with Session(engine) as session:
            doc = session.get(Document, document_id)
            if not doc:
                logger.error(f"Document ID {document_id} not found for ingestion.")
                return

            try:
                doc.status = "processing"
                session.add(doc)
                session.commit()

                # Step 1: Parse Document
                pages = DocumentParser.parse_file(doc.file_path, doc.file_type)
                doc.page_count = len(pages)

                # Save raw pages to DB
                for p in pages:
                    db_page = DocumentPage(
                        document_id=doc.id,
                        page_number=p.page_number,
                        raw_text=p.raw_text,
                        ocr_used=p.ocr_used
                    )
                    session.add(db_page)
                session.commit()

                # Step 2: Structure-Aware Chunking
                structured_chunks = chunker.chunk_document(
                    document_id=doc.id,
                    document_title=doc.title or doc.filename,
                    document_version=doc.version or "1.0",
                    effective_from=doc.effective_from,
                    effective_until=doc.effective_until,
                    pages=pages
                )

                if not structured_chunks:
                    doc.status = "ready"
                    doc.chunk_count = 0
                    session.add(doc)
                    session.commit()
                    return

                # Step 3: Embed Chunks
                chunk_texts = [c.text for c in structured_chunks]
                embeddings = embedding_service.embed_texts(chunk_texts)

                # Step 4: Prepare Vector DB Points & SQLite DB Records
                qdrant_points = []
                db_chunks = []

                for idx, (c, vec) in enumerate(zip(structured_chunks, embeddings)):
                    point_id = str(uuid.uuid4())
                    
                    db_chunk = Chunk(
                        document_id=doc.id,
                        page_number=c.page_number,
                        chunk_index=c.chunk_index,
                        section_heading=c.section_heading,
                        text=c.text,
                        token_count=c.token_count,
                        vector_id=point_id,
                        metadata_json=json.dumps(c.metadata)
                    )
                    db_chunks.append(db_chunk)

                    # Qdrant payload
                    payload = {
                        "document_id": doc.id,
                        "document_name": doc.title or doc.filename,
                        "version": doc.version or "1.0",
                        "document_version": doc.version or "1.0",
                        "page_number": c.page_number,
                        "source_page": c.page_number,
                        "section_heading": c.section_heading,
                        "section": c.section_heading,
                        "text": c.text,
                        "effective_from": doc.effective_from.isoformat() if doc.effective_from else None,
                        "effective_until": doc.effective_until.isoformat() if doc.effective_until else None,
                        "year": doc.effective_from.year if doc.effective_from else None,
                        "is_table": bool(c.metadata.get("is_table")),
                        "chunk_index": c.chunk_index
                    }

                    qdrant_points.append(
                        qmodels.PointStruct(
                            id=point_id,
                            vector=vec,
                            payload=payload
                        )
                    )

                # Step 5: Save to Qdrant and SQLite
                vector_db.upsert_chunks(qdrant_points)
                for chunk_obj in db_chunks:
                    session.add(chunk_obj)

                doc.chunk_count = len(db_chunks)
                doc.status = "ready"
                session.add(doc)
                session.commit()
                logger.info(f"Successfully processed document {doc.id} ({doc.filename}) into {len(db_chunks)} chunks.")

            except Exception as e:
                logger.exception(f"Failed to process document {document_id}: {e}")
                doc.status = "failed"
                doc.error_message = str(e)
                session.add(doc)
                session.commit()

ingestion_service = IngestionService()
