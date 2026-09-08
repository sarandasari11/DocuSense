import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel

# ----------------- Database ORM Models -----------------

class Document(SQLModel, table=True):
    __tablename__ = "documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_type: str  # pdf, docx, txt, img
    file_path: str
    title: Optional[str] = None
    version: Optional[str] = "1.0"
    effective_from: Optional[datetime.date] = None
    effective_until: Optional[datetime.date] = None
    page_count: int = 0
    chunk_count: int = 0
    status: str = "pending"  # pending, processing, ready, failed
    error_message: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    pages: List["DocumentPage"] = Relationship(back_populates="document", cascade_delete=True)
    chunks: List["Chunk"] = Relationship(back_populates="document", cascade_delete=True)


class DocumentPage(SQLModel, table=True):
    __tablename__ = "document_pages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    page_number: int
    raw_text: str
    ocr_used: bool = False
    
    document: Optional[Document] = Relationship(back_populates="pages")


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    page_number: int
    chunk_index: int
    section_heading: Optional[str] = "General"
    text: str
    token_count: int = 0
    vector_id: Optional[str] = None  # Qdrant point UUID
    metadata_json: Optional[str] = None  # JSON string of extra attributes
    
    document: Optional[Document] = Relationship(back_populates="chunks")


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = "New Conversation"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    messages: List["Message"] = Relationship(back_populates="conversation", cascade_delete=True)


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    role: str  # "user" | "assistant" | "system"
    content: str
    confidence_score: Optional[float] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    conversation: Optional[Conversation] = Relationship(back_populates="messages")
    citations: List["Citation"] = Relationship(back_populates="message", cascade_delete=True)


class Citation(SQLModel, table=True):
    __tablename__ = "citations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(foreign_key="messages.id", index=True)
    document_id: int = Field(foreign_key="documents.id")
    document_name: str
    page_number: int
    section_heading: Optional[str] = None
    excerpt: str
    relevance_score: float = 1.0
    
    message: Optional[Message] = Relationship(back_populates="citations")


class Contradiction(SQLModel, table=True):
    __tablename__ = "contradictions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_a_id: int = Field(foreign_key="documents.id")
    document_b_id: int = Field(foreign_key="documents.id")
    topic: str
    claim_a: str
    claim_b: str
    source_a_page: int
    source_b_page: int
    confidence: float
    status: str = "detected"  # detected, verified, resolved
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


# ----------------- API Pydantic Schemas -----------------

class DocumentRead(BaseModel):
    id: int
    filename: str
    file_type: str
    title: Optional[str] = None
    version: Optional[str] = None
    effective_from: Optional[datetime.date] = None
    effective_until: Optional[datetime.date] = None
    page_count: int
    chunk_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime.datetime

class CitationRead(BaseModel):
    document_id: int
    document_name: str
    page_number: int
    section_heading: Optional[str] = None
    excerpt: str
    relevance_score: float

class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    document_ids: Optional[List[int]] = None
    temporal_filter_year: Optional[int] = None
    use_reranker: bool = True
    use_hybrid: bool = True

class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    confidence_score: float
    citations: List[CitationRead]
    latency_ms: Dict[str, float]
    retrieved_chunks_count: int

class SearchQuery(BaseModel):
    query: str
    document_ids: Optional[List[int]] = None
    year: Optional[int] = None
    top_k: int = 5
    mode: str = "hybrid"  # "dense" | "sparse" | "hybrid"

class SearchResultItem(BaseModel):
    chunk_id: int
    document_id: int
    document_name: str
    page_number: int
    section_heading: Optional[str]
    text: str
    score: float
    retrieval_source: str  # "dense", "sparse", "reranked"

class CompareRequest(BaseModel):
    doc_a_id: int
    doc_b_id: int

class ClauseComparison(BaseModel):
    topic: str
    doc_a_section: Optional[str]
    doc_a_text: Optional[str]
    doc_a_page: Optional[int]
    doc_b_section: Optional[str]
    doc_b_text: Optional[str]
    doc_b_page: Optional[int]
    change_type: str  # "modified", "added", "removed", "unchanged"
    summary_of_change: str

class CompareResponse(BaseModel):
    doc_a_title: str
    doc_b_title: str
    comparison_matrix: List[ClauseComparison]
    contradictions_detected: List[Dict[str, Any]]
