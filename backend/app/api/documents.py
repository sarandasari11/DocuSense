import os
import shutil
import json
import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.config import settings
from app.database.db import get_session
from app.models.document import Document, DocumentRead, DocumentPage, Chunk
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

@router.post("/load-demo", response_model=List[DocumentRead])
def load_demo_documents(session: Session = Depends(get_session)):
    """Seed and ingest the 2024 and 2026 demo HR policies into the database and Qdrant index."""
    candidate_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sample_data")),
        os.path.abspath(os.path.join(os.getcwd(), "sample_data")),
        os.path.abspath(os.path.join(os.getcwd(), "backend", "sample_data")),
    ]
    sample_dir = None
    for p in candidate_paths:
        if os.path.exists(p):
            sample_dir = p
            break

    demo_files = [
        {
            "filename": "HR_Policy_2024.txt",
            "title": "HR Policy 2024",
            "version": "2024.1",
            "effective_from": datetime.date(2024, 1, 1),
            "content": (
                "ACME GLOBAL ENTERPRISES\n"
                "EMPLOYEE HANDBOOK AND POLICIES (2024 EDITION)\n"
                "Effective Date: January 1, 2024\n"
                "Policy ID: HR-2024-001\n\n"
                "1. GENERAL WORKING HOURS AND ATTENDANCE\n"
                "All standard full-time employees are expected to work 40 hours per week from 9:00 AM to 5:00 PM Monday through Friday.\n\n"
                "2. REMOTE WORK ALLOWANCE\n"
                "Employees are eligible for hybrid flexible working arrangements. Eligible employees may work remotely up to 2 days per week. "
                "Prior written approval from the departmental manager is mandatory before commencing remote work.\n\n"
                "3. ANNUAL LEAVE ENTITLEMENT\n"
                "Full-time personnel receive 20 days of paid annual vacation leave per calendar year. Unused leave may not be rolled over into the subsequent fiscal year.\n\n"
                "4. HEALTH AND REIMBURSEMENT\n"
                "The company provides comprehensive medical coverage and up to $500 annual wellness equipment reimbursement with receipt submission.\n"
            ),
        },
        {
            "filename": "HR_Policy_2026.txt",
            "title": "HR Policy 2026",
            "version": "2026.1",
            "effective_from": datetime.date(2026, 1, 1),
            "content": (
                "ACME GLOBAL ENTERPRISES\n"
                "EMPLOYEE HANDBOOK AND POLICIES (2026 EDITION)\n"
                "Effective Date: January 1, 2026\n"
                "Policy ID: HR-2026-017\n\n"
                "1. GENERAL WORKING HOURS AND ATTENDANCE\n"
                "All standard full-time employees are expected to work 40 hours per week with core collaboration hours between 10:00 AM and 4:00 PM.\n\n"
                "2. REMOTE WORK ALLOWANCE\n"
                "Under the modernized agile workplace initiative, eligible employees may work remotely up to 3 days per week. Departmental registration is recommended.\n\n"
                "3. ANNUAL LEAVE ENTITLEMENT\n"
                "Full-time personnel are granted 25 days of paid annual vacation leave per calendar year to promote work-life balance. Up to 5 days can be carried over.\n\n"
                "4. HEALTH AND REIMBURSEMENT\n"
                "The company provides comprehensive medical coverage, mental health counseling, and up to $1,000 annual wellness stipend.\n\n"
                "5. ARTIFICIAL INTELLIGENCE TOOLS USAGE\n"
                "Employees utilizing generative AI tools must adhere to the data privacy and IP security guidelines.\n"
            ),
        },
    ]

    loaded_docs = []
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    for item in demo_files:
        src_path = os.path.join(sample_dir, item["filename"]) if sample_dir else None

        existing = session.exec(
            select(Document).where(Document.filename == item["filename"])
        ).first()

        if existing and existing.status == "ready" and (existing.chunk_count or 0) > 0 and os.path.exists(existing.file_path):
            loaded_docs.append(existing)
            continue

        if existing:
            from sqlmodel import delete
            try:
                vector_db.delete_document_chunks(existing.id)
            except Exception:
                pass
            session.exec(delete(Chunk).where(Chunk.document_id == existing.id))
            session.exec(delete(DocumentPage).where(DocumentPage.document_id == existing.id))
            session.delete(existing)
            session.commit()

        dest_filename = f"{int(datetime.datetime.utcnow().timestamp())}_{item['filename']}"
        dest_path = os.path.join(settings.STORAGE_DIR, dest_filename)
        if src_path and os.path.exists(src_path):
            shutil.copyfile(src_path, dest_path)
        else:
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(item["content"])

        doc = Document(
            filename=item["filename"],
            file_type="txt",
            file_path=dest_path,
            title=item["title"],
            version=item["version"],
            effective_from=item["effective_from"],
            status="pending",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        ingestion_service.process_document(doc.id)
        session.refresh(doc)
        loaded_docs.append(doc)

    return loaded_docs

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


@router.get("/{document_id}/content")
def get_document_content(document_id: int, session: Session = Depends(get_session)):
    """Return extracted pages and indexed sections for source inspection."""
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = session.exec(
        select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
    ).all()
    chunks = session.exec(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
    ).all()
    return {
        "document": DocumentRead.model_validate(doc, from_attributes=True),
        "pages": [
            {
                "page_number": page.page_number,
                "raw_text": page.raw_text,
                "ocr_used": page.ocr_used,
            }
            for page in pages
        ],
        "sections": [
            {
                "chunk_id": chunk.id,
                "page_number": chunk.page_number,
                "section_heading": chunk.section_heading,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "metadata": json.loads(chunk.metadata_json) if chunk.metadata_json else {},
            }
            for chunk in chunks
        ],
    }


@router.get("/{document_id}/file")
def get_document_file(document_id: int, session: Session = Depends(get_session)):
    """Stream the original source file for the in-browser document reader."""
    doc = session.get(Document, document_id)
    if not doc or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Original document file not found")

    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
    }
    return FileResponse(doc.file_path, media_type=media_types.get(doc.file_type, "application/octet-stream"), filename=doc.filename)

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

