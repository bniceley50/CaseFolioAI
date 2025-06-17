import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base
class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    case_files = relationship('CaseFile', back_populates='owner')
class CaseFile(Base):
    __tablename__ = 'case_files'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_name = Column(String, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship('User', back_populates='case_files')
    documents = relationship('Document', back_populates='case_file', cascade='all, delete-orphan')
class Document(Base):
    __tablename__ = 'documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_file_id = Column(UUID(as_uuid=True), ForeignKey('case_files.id'), nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default='uploaded')
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    case_file = relationship('CaseFile', back_populates='documents')
    extracted_facts = relationship('ExtractedFact', back_populates='document', cascade='all, delete-orphan')
class ExtractedFact(Base):
    __tablename__ = 'extracted_facts'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    fact_type = Column(String, nullable=False)
    value = Column(String, nullable=False)
    page_number = Column(String, nullable=True)
    bounding_box = Column(JSON, nullable=True)
    confidence_score = Column(String, nullable=True)
    document = relationship('Document', back_populates='extracted_facts')