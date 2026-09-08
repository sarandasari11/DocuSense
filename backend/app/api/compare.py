from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from app.models.document import CompareRequest, CompareResponse
from app.services.comparison import document_comparator
from app.services.contradiction import contradiction_detector

router = APIRouter(prefix="/compare", tags=["Compare & Contradictions"])

@router.post("", response_model=CompareResponse)
def compare_document_versions(payload: CompareRequest):
    """Compare two documents to generate a section-by-section diff matrix and contradiction report."""
    try:
        diff_res = document_comparator.compare_documents(payload.doc_a_id, payload.doc_b_id)
        conflicts = contradiction_detector.detect_contradictions(payload.doc_a_id, payload.doc_b_id)
        diff_res.contradictions_detected = conflicts
        return diff_res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")

@router.post("/contradictions", response_model=List[Dict[str, Any]])
def get_contradictions(payload: CompareRequest):
    """Check for conflicting claims between two documents."""
    return contradiction_detector.detect_contradictions(payload.doc_a_id, payload.doc_b_id)
