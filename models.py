"""
CaseFolio AI - Production Database Models
Enterprise-grade SQLAlchemy 2.0 models with full audit trails and relationships
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, ForeignKey, Index, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class User(Base):
    """User account model with audit fields"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    case_files: Mapped[List["CaseFile"]] = relationship("CaseFile", back_populates="owner")
    api_keys: Mapped[List["APIKey"]] = relationship("APIKey", back_populates="user")


class CaseFile(Base):
    """Legal case file container"""
    __tablename__ = "case_files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True,
                                         default=lambda: f"CASE-{uuid.uuid4().hex[:8].upper()}")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active")
    
    # Foreign keys
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="case_files")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="case_file",
                                                      cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_case_owner", "owner_id", "status"),
    )


class Document(Base):
    """Document within a case file"""
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True,
                                           default=lambda: f"DOC-{uuid.uuid4().hex[:8].upper()}")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA-256 hash
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Document metadata
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Foreign keys
    case_file_id: Mapped[int] = mapped_column(ForeignKey("case_files.id"))
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    case_file: Mapped["CaseFile"] = relationship("CaseFile", back_populates="documents")
    uploaded_by: Mapped["User"] = relationship("User")
    extracted_facts: Mapped[List["ExtractedFact"]] = relationship("ExtractedFact", back_populates="document",
                                                                 cascade="all, delete-orphan")
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship("ProcessingJob", back_populates="document")


class ExtractedFact(Base):
    """Facts extracted from documents with precise location data"""
    __tablename__ = "extracted_facts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)  # date, amount, person_name
    value: Mapped[str] = mapped_column(Text, nullable=False)  # Stored as string, parsed as needed
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    
    # Location data for Click-to-Anchor™
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bounding_box: Mapped[List[float]] = mapped_column(JSON, nullable=False)  # [x0, y0, x1, y1]
    text_context: Mapped[Optional[str]] = mapped_column(Text)  # Surrounding text for context
    
    # Foreign keys
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    
    # Timestamps
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extracted_facts")
    event_facts: Mapped[List["EventFact"]] = relationship("EventFact", back_populates="fact")
    
    __table_args__ = (
        Index("idx_fact_type_doc", "fact_type", "document_id"),
        Index("idx_fact_page", "document_id", "page_number"),
    )


class SynthesizedEvent(Base):
    """AI-synthesized events from extracted facts"""
    __tablename__ = "synthesized_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_description: Mapped[str] = mapped_column(Text, nullable=False)
    event_category: Mapped[str] = mapped_column(String(50))  # medical, legal, financial, etc.
    confidence_score: Mapped[float] = mapped_column(Float, default=0.95)
    
    # AI metadata
    llm_model: Mapped[Optional[str]] = mapped_column(String(50))
    llm_tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Foreign keys
    case_file_id: Mapped[int] = mapped_column(ForeignKey("case_files.id"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    case_file: Mapped["CaseFile"] = relationship("CaseFile")
    source_facts: Mapped[List["ExtractedFact"]] = relationship(
        "ExtractedFact",
        secondary="event_facts",
        viewonly=True
    )
    event_facts: Mapped[List["EventFact"]] = relationship("EventFact", back_populates="event")
    
    __table_args__ = (
        Index("idx_event_date_case", "event_date", "case_file_id"),
    )


class EventFact(Base):
    """Association table linking events to their source facts"""
    __tablename__ = "event_facts"
    
    event_id: Mapped[int] = mapped_column(ForeignKey("synthesized_events.id"), primary_key=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("extracted_facts.id"), primary_key=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    
    # Relationships
    event: Mapped["SynthesizedEvent"] = relationship("SynthesizedEvent", back_populates="event_facts")
    fact: Mapped["ExtractedFact"] = relationship("ExtractedFact", back_populates="event_facts")


class Contradiction(Base):
    """Detected contradictions between events"""
    __tablename__ = "contradictions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event1_id: Mapped[int] = mapped_column(ForeignKey("synthesized_events.id"))
    event2_id: Mapped[int] = mapped_column(ForeignKey("synthesized_events.id"))
    contradiction_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))  # high, medium, low
    explanation: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float)
    
    # AI metadata
    llm_model: Mapped[Optional[str]] = mapped_column(String(50))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    event1: Mapped["SynthesizedEvent"] = relationship("SynthesizedEvent", foreign_keys=[event1_id])
    event2: Mapped["SynthesizedEvent"] = relationship("SynthesizedEvent", foreign_keys=[event2_id])
    
    __table_args__ = (
        Index("idx_contradiction_events", "event1_id", "event2_id"),
    )


class ProcessingJob(Base):
    """Background job tracking for document processing"""
    __tablename__ = "processing_jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(50))  # document_processing, reanalysis, etc.
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, processing, completed, failed
    progress: Mapped[Optional[dict]] = mapped_column(JSON)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Foreign keys
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="processing_jobs")
    created_by: Mapped["User"] = relationship("User")


class APIKey(Base):
    """API keys for authentication"""
    __tablename__ = "api_keys"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)  # First 8 chars for lookup
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt hash
    name: Mapped[str] = mapped_column(String(100))
    scopes: Mapped[List[str]] = mapped_column(JSON, default=list)  # Permissions
    
    # Rate limiting
    rate_limit: Mapped[Optional[int]] = mapped_column(Integer, default=1000)  # Requests per hour
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")
    
    @property
    def is_active(self) -> bool:
        """Check if API key is currently active"""
        if self.revoked_at:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True