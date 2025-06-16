"""
CaseFolio AI - Production Asynchronous Task Definitions
Document processing pipeline with real PDF extraction, coordinate-level precision, and database persistence
"""

from celery import Task
from celery_app import app, TaskStates
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import json
import logging
import os
import tempfile
from pathlib import Path
from sqlalchemy.orm import Session

# Import our production modules
from pdf_processor import PDFProcessor
from event_synthesizer import EventSynthesizer
from contradiction_analyzer import ContradictionAnalyzer
from trust_engine_mvp_sprint2 import ExtractedFact as LegacyExtractedFact, SourceLink

# Import database models
from models import (
    Document, ExtractedFact, SynthesizedEvent, EventFact, 
    Contradiction, ProcessingJob, CaseFile
)

# Configure logging
logger = logging.getLogger(__name__)


class ProcessDocumentTask(Task):
    """
    Custom Celery task class for document processing with progress tracking
    """
    
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.synthesizer = EventSynthesizer()
        self.analyzer = ContradictionAnalyzer()
    
    def update_task_state(self, state: str, meta: Dict[str, Any] = None):
        """Update task state with metadata"""
        self.update_state(
            state=state,
            meta=meta or {}
        )


@app.task(bind=True, base=ProcessDocumentTask, name='tasks.process_document')
def process_document(self, document_id: str, db_session: Session = None) -> Dict[str, Any]:
    """
    Production document processing pipeline with real PDF extraction and database persistence
    
    Args:
        document_id: Document ID from database
        db_session: SQLAlchemy database session
        
    Returns:
        Processed results including facts with precise coordinates, events, and contradictions
    """
    result = {
        'document_id': document_id,
        'status': 'processing',
        'stages': {},
        'facts_count': 0,
        'events_count': 0,
        'contradictions_count': 0,
        'errors': []
    }
    
    try:
        # Get document from database
        document = db_session.query(Document).filter_by(document_id=document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Update processing job status
        job = db_session.query(ProcessingJob).filter_by(
            document_id=document.id
        ).order_by(ProcessingJob.created_at.desc()).first()
        
        if job:
            job.status = 'processing'
            job.started_at = datetime.utcnow()
            db_session.commit()
        
        # Stage 1: PARSING
        self.update_task_state(
            state=TaskStates.PARSING,
            meta={
                'current': 1,
                'total': 4,
                'status': 'Parsing document structure...'
            }
        )
        
        # Process PDF with coordinate extraction
        doc_data = self.pdf_processor.process_pdf(document.storage_path)
        
        # Update document metadata
        document.page_count = doc_data['total_pages']
        document.metadata = doc_data.get('metadata', {})
        db_session.commit()
        
        result['stages']['parsing'] = {
            'status': 'completed',
            'pages_parsed': doc_data['total_pages'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Stage 2: EXTRACTING with precise coordinates
        self.update_task_state(
            state=TaskStates.EXTRACTING,
            meta={
                'current': 2,
                'total': 4,
                'status': 'Extracting facts with coordinate precision...'
            }
        )
        
        # Extract facts from each page and save to database
        all_legacy_facts = []  # For AI processing
        fact_id_map = {}  # Map legacy facts to database IDs
        
        for page_data in doc_data['pages']:
            page_facts = self.pdf_processor.extract_facts_with_positions(
                page_data, document.filename
            )
            
            for fact_data in page_facts:
                # Create database fact record
                db_fact = ExtractedFact(
                    document_id=document.id,
                    fact_type=fact_data['fact_type'],
                    value=str(fact_data['value']),
                    page_number=fact_data['page_number'],
                    bounding_box=fact_data['bounding_box'],
                    text_context=fact_data.get('text_match', ''),
                    confidence_score=0.99  # High confidence for deterministic extraction
                )
                db_session.add(db_fact)
                db_session.flush()  # Get the ID
                
                # Create legacy fact for AI processing
                source_link = SourceLink(
                    document_name=document.filename,
                    page_number=fact_data['page_number'],
                    bounding_box=fact_data['bounding_box']
                )
                
                legacy_fact = LegacyExtractedFact(
                    value=fact_data['value'],
                    fact_type=fact_data['fact_type'],
                    source=source_link
                )
                all_legacy_facts.append(legacy_fact)
                fact_id_map[id(legacy_fact)] = db_fact.id
        
        db_session.commit()
        result['facts_count'] = len(all_legacy_facts)
        
        result['stages']['extracting'] = {
            'status': 'completed',
            'facts_found': len(all_legacy_facts),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Stage 3: SYNTHESIZING
        self.update_task_state(
            state=TaskStates.SYNTHESIZING,
            meta={
                'current': 3,
                'total': 4,
                'status': 'Synthesizing events with AI...'
            }
        )
        
        # Synthesize events using AI
        synthesized_events = self.synthesizer.synthesize_events(all_legacy_facts)
        
        # Save events to database
        event_id_map = {}
        for event in synthesized_events:
            # Determine category
            category = self._categorize_event(event.event_description)
            
            db_event = SynthesizedEvent(
                case_file_id=document.case_file_id,
                event_date=datetime.combine(event.event_date, datetime.min.time()),
                event_description=event.event_description,
                event_category=category,
                confidence_score=getattr(event, 'confidence', 0.95),
                llm_model='gpt-3.5-turbo',
                llm_tokens_used=100  # Approximate
            )
            db_session.add(db_event)
            db_session.flush()
            
            # Link events to source facts
            for source_fact in event.source_facts:
                fact_db_id = fact_id_map.get(id(source_fact))
                if fact_db_id:
                    event_fact = EventFact(
                        event_id=db_event.id,
                        fact_id=fact_db_id,
                        relevance_score=0.9
                    )
                    db_session.add(event_fact)
            
            event_id_map[id(event)] = db_event.id
        
        db_session.commit()
        result['events_count'] = len(synthesized_events)
        
        result['stages']['synthesizing'] = {
            'status': 'completed',
            'events_created': len(synthesized_events),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Stage 4: ANALYZING for contradictions
        self.update_task_state(
            state=TaskStates.ANALYZING,
            meta={
                'current': 4,
                'total': 4,
                'status': 'Analyzing for contradictions...'
            }
        )
        
        # Analyze contradictions
        contradictions = self.analyzer.analyze_contradictions(synthesized_events)
        
        # Save contradictions to database
        for contra in contradictions:
            # Find the database event IDs
            event1_id = None
            event2_id = None
            
            # Match events by description (simplified)
            for event in synthesized_events:
                db_id = event_id_map.get(id(event))
                if db_id:
                    if contra.get('event1_description') in event.event_description:
                        event1_id = db_id
                    elif contra.get('event2_description') in event.event_description:
                        event2_id = db_id
            
            if event1_id and event2_id:
                db_contradiction = Contradiction(
                    event1_id=event1_id,
                    event2_id=event2_id,
                    contradiction_type=contra.get('type', 'timeline'),
                    severity=contra.get('severity', 'medium'),
                    explanation=contra.get('explanation', ''),
                    confidence_score=contra.get('confidence', 0.8),
                    llm_model='gpt-4'
                )
                db_session.add(db_contradiction)
        
        db_session.commit()
        result['contradictions_count'] = len(contradictions)
        
        result['stages']['analyzing'] = {
            'status': 'completed',
            'contradictions_found': len(contradictions),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Update document as processed
        document.processed_at = datetime.utcnow()
        
        # Update job as completed
        if job:
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.result = result
        
        db_session.commit()
        
        # Final success state
        result['status'] = 'success'
        result['completed_at'] = datetime.utcnow().isoformat()
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        result['status'] = 'failed'
        result['errors'].append({
            'type': 'processing_error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Update job as failed
        if job:
            job.status = 'failed'
            job.error = {'message': str(e), 'type': type(e).__name__}
            job.completed_at = datetime.utcnow()
            db_session.commit()
        
        # Update state to failure
        self.update_task_state(
            state=TaskStates.FAILURE,
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        
        raise
    
    def _categorize_event(self, description: str) -> str:
        """Categorize an event based on its description."""
        description_lower = description.lower()
        
        if any(term in description_lower for term in ['medical', 'hospital', 'doctor', 'treatment', 'injury', 'pain']):
            return 'medical'
        elif any(term in description_lower for term in ['legal', 'filing', 'court', 'lawsuit', 'claim']):
            return 'legal'
        elif any(term in description_lower for term in ['payment', 'cost', 'expense', 'bill', '$']):
            return 'financial'
        elif any(term in description_lower for term in ['email', 'letter', 'call', 'meeting']):
            return 'communication'
        else:
            return 'general'


@app.task(name='tasks.process_case_file')
def process_case_file(case_file_id: int, document_content: str, document_name: str, 
                     db_session: Session = None) -> Dict[str, Any]:
    """
    Process a text document for a case file (backwards compatibility)
    
    Args:
        case_file_id: Case file ID from database
        document_content: Raw document text
        document_name: Document filename
        db_session: Database session
        
    Returns:
        Job information
    """
    try:
        # Save document content to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(document_content)
            tmp_path = tmp_file.name
        
        # Create document record
        document = Document(
            case_file_id=case_file_id,
            filename=document_name,
            content_type='text/plain',
            file_size=len(document_content),
            storage_path=tmp_path,
            uploaded_by_id=1  # System user
        )
        db_session.add(document)
        db_session.flush()
        
        # Create processing job
        job = ProcessingJob(
            job_id=f"job_{document.document_id}",
            job_type='document_processing',
            document_id=document.id,
            created_by_id=1,  # System user
            status='pending'
        )
        db_session.add(job)
        db_session.commit()
        
        # Trigger async processing
        task = process_document.delay(document.document_id)
        
        return {
            'job_id': job.job_id,
            'document_id': document.document_id,
            'task_id': task.id,
            'status': 'queued'
        }
        
    except Exception as e:
        logger.error(f"Error creating processing job: {str(e)}")
        raise


@app.task(name='tasks.get_processing_results')
def get_processing_results(job_id: str, db_session: Session = None) -> Dict[str, Any]:
    """
    Get results for a processing job with all extracted data
    
    Args:
        job_id: Processing job ID
        db_session: Database session
        
    Returns:
        Complete processing results with facts, events, and contradictions
    """
    try:
        # Get job
        job = db_session.query(ProcessingJob).filter_by(job_id=job_id).first()
        if not job:
            return {'error': 'Job not found', 'status': 'not_found'}
        
        # Build response based on job status
        response = {
            'job_id': job_id,
            'status': job.status,
            'created_at': job.created_at.isoformat(),
            'progress': job.progress or {}
        }
        
        if job.status == 'completed' and job.document_id:
            # Get all data for this document
            document = db_session.query(Document).get(job.document_id)
            
            # Get facts
            facts = db_session.query(ExtractedFact).filter_by(
                document_id=document.id
            ).all()
            
            # Get events
            events = db_session.query(SynthesizedEvent).filter_by(
                case_file_id=document.case_file_id
            ).all()
            
            # Get contradictions
            event_ids = [e.id for e in events]
            contradictions = db_session.query(Contradiction).filter(
                (Contradiction.event1_id.in_(event_ids)) |
                (Contradiction.event2_id.in_(event_ids))
            ).all()
            
            # Format response
            response['result'] = {
                'document_name': document.filename,
                'total_pages': document.page_count,
                'facts': [{
                    'id': f.id,
                    'type': f.fact_type,
                    'value': f.value,
                    'page': f.page_number,
                    'bounding_box': f.bounding_box,
                    'confidence': f.confidence_score,
                    'source': {
                        'page_number': f.page_number,
                        'bounding_box': f.bounding_box
                    }
                } for f in facts],
                'events': [{
                    'id': e.id,
                    'event_date': e.event_date.isoformat(),
                    'event_description': e.event_description,
                    'category': e.event_category,
                    'confidence_score': e.confidence_score,
                    'source_facts': [{
                        'id': ef.fact_id,
                        'type': ef.fact.fact_type,
                        'value': ef.fact.value
                    } for ef in e.event_facts]
                } for e in events],
                'contradictions': [{
                    'id': c.id,
                    'event1_id': c.event1_id,
                    'event2_id': c.event2_id,
                    'type': c.contradiction_type,
                    'severity': c.severity,
                    'explanation': c.explanation,
                    'confidence': c.confidence_score
                } for c in contradictions],
                'pages': []  # Would need to store page data separately
            }
            
            response['completed_at'] = job.completed_at.isoformat()
            
        elif job.status == 'failed':
            response['error'] = job.error
            
        return response
        
    except Exception as e:
        logger.error(f"Error getting processing results: {str(e)}")
        return {'error': str(e), 'status': 'error'}


@app.task(name='tasks.reanalyze_case')
def reanalyze_case(case_file_id: int, db_session: Session = None) -> Dict[str, Any]:
    """
    Re-run AI analysis on all facts in a case
    
    Args:
        case_file_id: Case file ID
        db_session: Database session
        
    Returns:
        Analysis results
    """
    try:
        # Get all facts for this case
        facts = db_session.query(ExtractedFact).join(Document).filter(
            Document.case_file_id == case_file_id
        ).all()
        
        # Convert to legacy format for AI processing
        legacy_facts = []
        fact_map = {}
        
        for fact in facts:
            source = SourceLink(
                document_name=fact.document.filename,
                page_number=fact.page_number,
                bounding_box=fact.bounding_box
            )
            
            # Parse value based on type
            value = fact.value
            if fact.fact_type == 'date':
                try:
                    value = datetime.fromisoformat(value).date()
                except:
                    continue
            elif fact.fact_type == 'amount':
                try:
                    value = float(value.replace('$', '').replace(',', ''))
                except:
                    continue
            
            legacy_fact = LegacyExtractedFact(
                value=value,
                fact_type=fact.fact_type,
                source=source
            )
            legacy_facts.append(legacy_fact)
            fact_map[id(legacy_fact)] = fact.id
        
        # Delete old events and contradictions
        old_events = db_session.query(SynthesizedEvent).filter_by(
            case_file_id=case_file_id
        ).all()
        
        for event in old_events:
            db_session.delete(event)
        
        db_session.commit()
        
        # Re-synthesize events
        synthesizer = EventSynthesizer()
        new_events = synthesizer.synthesize_events(legacy_facts)
        
        # Save new events
        for event in new_events:
            db_event = SynthesizedEvent(
                case_file_id=case_file_id,
                event_date=datetime.combine(event.event_date, datetime.min.time()),
                event_description=event.event_description,
                event_category='general',  # Would need categorization
                confidence_score=0.95,
                llm_model='gpt-3.5-turbo'
            )
            db_session.add(db_event)
            db_session.flush()
            
            # Link to facts
            for source_fact in event.source_facts:
                fact_id = fact_map.get(id(source_fact))
                if fact_id:
                    event_fact = EventFact(
                        event_id=db_event.id,
                        fact_id=fact_id
                    )
                    db_session.add(event_fact)
        
        # Re-analyze contradictions
        analyzer = ContradictionAnalyzer()
        contradictions = analyzer.analyze_contradictions(new_events)
        
        # Save contradictions (would need proper mapping)
        
        db_session.commit()
        
        return {
            'status': 'success',
            'events_created': len(new_events),
            'contradictions_found': len(contradictions)
        }
        
    except Exception as e:
        logger.error(f"Error reanalyzing case: {str(e)}")
        raise


@app.task(name='tasks.cleanup_old_jobs')
def cleanup_old_jobs(days_old: int = 30) -> Dict[str, int]:
    """
    Clean up old processing jobs and temporary files
    
    Args:
        days_old: Delete jobs older than this many days
        
    Returns:
        Cleanup statistics
    """
    logger.info(f"Cleaning up jobs older than {days_old} days")
    
    # This would need database session to clean up old jobs
    # For now, just clean temporary files
    
    temp_dir = tempfile.gettempdir()
    current_time = time.time()
    cleaned_files = 0
    
    for filename in os.listdir(temp_dir):
        if filename.endswith(('.pdf', '.txt')):
            filepath = os.path.join(temp_dir, filename)
            try:
                file_age_days = (current_time - os.path.getmtime(filepath)) / 86400
                if file_age_days > days_old:
                    os.remove(filepath)
                    cleaned_files += 1
            except Exception as e:
                logger.warning(f"Failed to clean up {filepath}: {str(e)}")
    
    return {'cleaned_files': cleaned_files}