from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database.db import get_session
from app.models.document import ChatRequest, ChatResponse, Conversation, Message, Citation
from app.services.rag import rag_engine

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/conversations")
def list_conversations(session: Session = Depends(get_session)):
    conversations = session.exec(select(Conversation).order_by(Conversation.created_at.desc())).all()
    return [
        {"id": item.id, "title": item.title, "created_at": item.created_at}
        for item in conversations
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = session.exec(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    ).all()
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "confidence_score": message.confidence_score,
                "created_at": message.created_at,
                "citations": [
                    {
                        "document_id": citation.document_id,
                        "document_name": citation.document_name,
                        "page_number": citation.page_number,
                        "section_heading": citation.section_heading,
                        "excerpt": citation.excerpt,
                        "relevance_score": citation.relevance_score,
                    }
                    for citation in message.citations
                ],
            }
            for message in messages
        ],
    }


@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: int, payload: dict, session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="Conversation title cannot be empty")
    conversation.title = title[:120]
    session.add(conversation)
    session.commit()
    return {"id": conversation.id, "title": conversation.title}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session.delete(conversation)
    session.commit()
    return {"status": "deleted", "id": conversation_id}

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
