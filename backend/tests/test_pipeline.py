import os
import sys
from datetime import date
from sqlmodel import Session, select

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.database.db import init_db, engine
from app.models.document import Document, Chunk
from app.services.ingestion import ingestion_service
from app.services.retrieval import hybrid_retriever
from app.services.rag import rag_engine
from app.services.comparison import document_comparator
from app.services.contradiction import contradiction_detector

def test_full_docusense_pipeline():
    # 1. Initialize DB and reset tables for clean test run
    init_db()
    with Session(engine) as session:
        session.exec(select(Chunk)).all()
        from sqlmodel import delete
        session.exec(delete(Chunk))
        session.exec(delete(Document))
        session.commit()
    
    # 2. Ingest 2024 Policy
    sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample_data"))
    path_2024 = os.path.join(sample_dir, "HR_Policy_2024.txt")
    with Session(engine) as session:
        doc_2024 = Document(
            filename="HR_Policy_2024.txt",
            file_type="txt",
            file_path=path_2024,
            title="HR Policy 2024",
            version="2024.1",
            effective_from=date(2024, 1, 1),
            status="pending"
        )
        session.add(doc_2024)
        session.commit()
        session.refresh(doc_2024)
        doc_2024_id = doc_2024.id

    ingestion_service.process_document(doc_2024_id)

    # 3. Ingest 2026 Policy
    path_2026 = os.path.join(sample_dir, "HR_Policy_2026.txt")
    with Session(engine) as session:
        doc_2026 = Document(
            filename="HR_Policy_2026.txt",
            file_type="txt",
            file_path=path_2026,
            title="HR Policy 2026",
            version="2026.1",
            effective_from=date(2026, 1, 1),
            status="pending"
        )
        session.add(doc_2026)
        session.commit()
        session.refresh(doc_2026)
        doc_2026_id = doc_2026.id

    ingestion_service.process_document(doc_2026_id)

    # Assert documents are processed
    with Session(engine) as session:
        d24 = session.get(Document, doc_2024_id)
        d26 = session.get(Document, doc_2026_id)
        assert d24.status == "ready"
        assert d26.status == "ready"
        assert d24.chunk_count > 0
        assert d26.chunk_count > 0

    # 4. Test Keyword Search on exact Policy ID
    bm25_res = hybrid_retriever.search_sparse_bm25("HR-2026-017")
    assert len(bm25_res) > 0
    assert bm25_res[0]["document_id"] == doc_2026_id

    # 5. Test Hybrid Retrieval
    hybrid_res = hybrid_retriever.hybrid_search("remote work allowance days", limit=5)
    assert len(hybrid_res) > 0
    assert any("remote" in c.text.lower() for c in hybrid_res)

    # 6. Test Temporal Filtering (Query for 2024)
    chat_2024_res = rag_engine.answer_query(
        query="What is the remote work policy in 2024?",
        conversation_id=1,
        year=2024
    )
    assert chat_2024_res is not None
    assert len(chat_2024_res.citations) > 0
    assert chat_2024_res.citations[0].document_id == doc_2024_id

    # 7. Test Document Version Comparison
    diff = document_comparator.compare_documents(doc_2024_id, doc_2026_id)
    assert diff.doc_a_title == "HR Policy 2024"
    assert diff.doc_b_title == "HR Policy 2026"
    assert len(diff.comparison_matrix) > 0

    # 8. Test Contradiction Detection
    conflicts = contradiction_detector.detect_contradictions(doc_2024_id, doc_2026_id)
    assert len(conflicts) > 0
    print("\n--- Detected Contradictions ---")
    for c in conflicts:
        print(f"Topic: {c['topic']} | Reason: {c['conflict_reason']}")

    print("\nAll DocuSense pipeline tests passed successfully!")

if __name__ == "__main__":
    test_full_docusense_pipeline()
