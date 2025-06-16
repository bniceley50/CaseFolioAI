"""
CaseFolio AI - Demo Mode
Run without Redis/Celery for testing and development
"""

import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import uvicorn

# Import our modules
from intelligence_engine_phase2 import process_document as sync_process_document
from event_synthesizer import EventSynthesizer
from contradiction_analyzer import ContradictionAnalyzer

# Create FastAPI app
app = FastAPI(title="CaseFolio AI Demo Mode")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (for demo mode)
jobs = {}

# Request/Response models
class ProcessCaseFileRequest(BaseModel):
    case_id: str
    document_name: str
    document_content: str

class ProcessCaseFileResponse(BaseModel):
    job_id: str
    case_id: str
    status: str
    created_at: datetime

# Demo processing function
async def process_document_demo(job_id: str, document_content: str, document_name: str, case_id: str):
    """Process document synchronously for demo mode"""
    try:
        # Update status
        jobs[job_id] = {
            'state': 'PARSING',
            'progress': {'current': 1, 'total': 4, 'status': 'Parsing document...'}
        }
        await asyncio.sleep(1)  # Simulate processing
        
        # Extract facts
        jobs[job_id] = {
            'state': 'EXTRACTING',
            'progress': {'current': 2, 'total': 4, 'status': 'Extracting facts...'}
        }
        facts, _ = sync_process_document(document_content, document_name)
        await asyncio.sleep(1)
        
        # Synthesize events
        jobs[job_id] = {
            'state': 'SYNTHESIZING',
            'progress': {'current': 3, 'total': 4, 'status': 'Synthesizing events with AI...'}
        }
        synthesizer = EventSynthesizer()
        events = synthesizer.synthesize_events(facts)
        await asyncio.sleep(1)
        
        # Analyze contradictions
        jobs[job_id] = {
            'state': 'ANALYZING',
            'progress': {'current': 4, 'total': 4, 'status': 'Analyzing contradictions...'}
        }
        analyzer = ContradictionAnalyzer()
        contradictions = analyzer.analyze_contradictions(events)
        await asyncio.sleep(1)
        
        # Format results
        result = {
            'case_id': case_id,
            'document_name': document_name,
            'status': 'success',
            'facts': [
                {
                    'id': idx,
                    'type': fact.fact_type,
                    'value': str(fact.value),
                    'page': fact.source.page_number
                }
                for idx, fact in enumerate(facts, 1)
            ],
            'events': [
                {
                    'id': idx,
                    'date': event.event_date.isoformat(),
                    'description': event.event_description,
                    'confidence': 0.95
                }
                for idx, event in enumerate(events, 1)
            ],
            'contradictions': contradictions
        }
        
        jobs[job_id] = {
            'state': 'SUCCESS',
            'progress': {'current': 4, 'total': 4, 'status': 'Complete'},
            'result': result
        }
        
    except Exception as e:
        jobs[job_id] = {
            'state': 'FAILURE',
            'error': {'message': str(e)}
        }

# API Endpoints
@app.post("/process-case-file/", response_model=ProcessCaseFileResponse)
async def process_case_file(request: ProcessCaseFileRequest):
    """Queue document processing (demo mode)"""
    job_id = f"demo-{datetime.now().timestamp()}"
    
    # Start processing in background
    asyncio.create_task(
        process_document_demo(
            job_id,
            request.document_content,
            request.document_name,
            request.case_id
        )
    )
    
    return ProcessCaseFileResponse(
        job_id=job_id,
        case_id=request.case_id,
        status="queued",
        created_at=datetime.utcnow()
    )

@app.get("/results/{job_id}")
async def get_results(job_id: str):
    """Get job results (demo mode)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        'job_id': job_id,
        'state': job.get('state', 'PENDING'),
        'progress': job.get('progress', {}),
        'result': job.get('result'),
        'error': job.get('error')
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        'status': 'healthy',
        'mode': 'demo',
        'timestamp': datetime.utcnow()
    }

if __name__ == "__main__":
    print("\n" + "="*50)
    print("CaseFolio AI - DEMO MODE")
    print("="*50)
    print("\nRunning without Redis/Celery for testing")
    print("\nAPI running at: http://localhost:8000")
    print("API docs at: http://localhost:8000/docs")
    print("\nOpen chronoanchor_workbench.html in your browser")
    print("\nPress Ctrl+C to stop")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)