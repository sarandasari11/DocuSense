import os
import shutil
import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.config import settings
from app.database.db import get_session
from app.models.document import Document, DocumentRead
from app.services.ingestion import ingestion_service
from app.database.vector_db import vector_db

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentRead)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    version: Optional[str] = Form("1.0"),
    effective_from: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    """Upload a document and trigger structure-aware parsing and vector indexing."""
    filename = file.filename
    ext = filename.split(".")[-1].lower() if "." in filename else "txt"
    
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    saved_path = os.path.join(settings.STORAGE_DIR, f"{int(datetime.datetime.utcnow().timestamp())}_{filename}")
    
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    eff_date = None
    if effective_from:
        try:
            eff_date = datetime.date.fromisoformat(effective_from)
        except Exception:
            pass

    doc = Document(
        filename=filename,
        file_type=ext,
        file_path=saved_path,
        title=title or filename,
        version=version or "1.0",
        effective_from=eff_date,
        status="pending"
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # Process ingestion synchronously or in background
    ingestion_service.process_document(doc.id)
    session.refresh(doc)

    return doc

@router.get("", response_model=List[DocumentRead])
def list_documents(session: Session = Depends(get_session)):
    """List all registered documents."""
    docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
    return docs

@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, session: Session = Depends(get_session)):
    """Retrieve details of a specific document."""
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.delete("/{document_id}")
def delete_document(document_id: int, session: Session = Depends(get_session)):
    """Delete a document, all its chunks, pages, and vector embeddings."""
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Delete vector embeddings
    try:
        vector_db.delete_document_chunks(document_id)
    except Exception as e:
        pass

    # 2. Delete file from storage
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    # 3. Explicitly delete associated chunks and pages
    from app.models.document import DocumentPage, Chunk
    from sqlmodel import delete
    session.exec(delete(Chunk).where(Chunk.document_id == document_id))
    session.exec(delete(DocumentPage).where(DocumentPage.document_id == document_id))

    # 4. Delete document record
    session.delete(doc)
    session.commit()
    return {"status": "success", "message": f"Document {document_id} and all indexed data deleted."}

@router.delete("")
def delete_all_documents(session: Session = Depends(get_session)):
    """Delete all indexed documents, chunks, and reset repository."""
    from app.models.document import DocumentPage, Chunk
    from sqlmodel import delete
    
    docs = session.exec(select(Document)).all()
    for doc in docs:
        try:
            vector_db.delete_document_chunks(doc.id)
        except Exception:
            pass
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception:
                pass

    session.exec(delete(Chunk))
    session.exec(delete(DocumentPage))
    session.exec(delete(Document))
    session.commit()
    return {"status": "success", "message": "All documents and index data cleared."}

