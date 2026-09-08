from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database.db import get_session
from app.models.document import ChatRequest, ChatResponse, Conversation, Message, Citation
from app.services.rag import rag_engine

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("", response_model=ChatResponse)
def chat_with_documents(payload: ChatRequest, session: Session = Depends(get_session)):
    """Ask a question across indexed documents with grounded citations."""
    # Resolve Conversation ID
    if payload.conversation_id:
        conv = session.get(Conversation, payload.conversation_id)
        if not conv:
            conv = Conversation(title=payload.question[:40])
            session.add(conv)
            session.commit()
            session.refresh(conv)
    else:
        conv = Conversation(title=payload.question[:40])
        session.add(conv)
        session.commit()
        session.refresh(conv)

    # Save User message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=payload.question
    )
    session.add(user_msg)
    session.commit()

    # Invoke RAG Engine
    response = rag_engine.answer_query(
        query=payload.question,
        conversation_id=conv.id,
        document_ids=payload.document_ids,
        year=payload.temporal_filter_year,
        versions=payload.document_versions,
        use_reranker=payload.use_reranker,
        use_hybrid=payload.use_hybrid,
        answer_only_from_documents=payload.answer_only_from_documents
    )

    # Save Assistant message
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=response.answer,
        confidence_score=response.confidence_score
    )
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)

    # Save Citations
    for cite in response.citations:
        db_cite = Citation(
            message_id=assistant_msg.id,
            document_id=cite.document_id,
            document_name=cite.document_name,
            page_number=cite.page_number,
            section_heading=cite.section_heading,
            excerpt=cite.excerpt,
            relevance_score=cite.relevance_score
        )
        session.add(db_cite)
    session.commit()

    return response
