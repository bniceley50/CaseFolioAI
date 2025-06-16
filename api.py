"""
CaseFolio AI - FastAPI Application
RESTful API endpoints for document processing and job management
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import logging

from celery_app import app as celery_app
from tasks import process_document

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CaseFolio AI API",
    description="AI-powered legal document analysis platform",
    version="1.0.0"
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class ProcessCaseFileRequest(BaseModel):
    case_id: str = Field(description="Unique case identifier")
    document_name: str = Field(description="Name of the document")
    document_content: str = Field(description="Raw document text content")


class ProcessCaseFileResponse(BaseModel):
    job_id: str = Field(description="Unique job identifier for tracking")
    case_id: str = Field(description="Case identifier")
    status: str = Field(description="Initial job status")
    created_at: datetime = Field(description="Job creation timestamp")


class JobStatusResponse(BaseModel):
    job_id: str
    state: str = Field(description="Current job state")
    progress: Dict[str, Any] = Field(description="Progress information")
    result: Optional[Dict[str, Any]] = Field(description="Final results if complete")
    error: Optional[Dict[str, Any]] = Field(description="Error details if failed")


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, str]


# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "CaseFolio AI API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    # Check Celery connection
    celery_status = "healthy"
    try:
        # Inspect active workers
        i = celery_app.control.inspect()
        stats = i.stats()
        if not stats:
            celery_status = "no workers"
    except Exception as e:
        celery_status = f"error: {str(e)}"
    
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        services={
            "api": "healthy",
            "celery": celery_status
        }
    )


@app.post("/process-case-file/", response_model=ProcessCaseFileResponse)
async def process_case_file(request: ProcessCaseFileRequest):
    """
    Queue a document for processing
    
    Initiates asynchronous document processing pipeline:
    1. PARSING - Document structure analysis
    2. EXTRACTING - Deterministic fact extraction
    3. SYNTHESIZING - AI-powered event synthesis
    4. ANALYZING - Contradiction detection
    """
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Queue the task
        task = process_document.apply_async(
            args=[request.document_content, request.document_name, request.case_id],
            task_id=job_id
        )
        
        logger.info(f"Queued document processing job: {job_id}")
        
        return ProcessCaseFileResponse(
            job_id=job_id,
            case_id=request.case_id,
            status="queued",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error queuing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-case-file/", response_model=ProcessCaseFileResponse)
async def upload_case_file(
    case_id: str,
    file: UploadFile = File(...)
):
    """
    Upload and process a document file
    
    Accepts PDF, TXT, or other document formats
    """
    try:
        # Read file content
        content = await file.read()
        
        # For MVP, assume text content
        # In production, implement proper file parsing
        document_content = content.decode('utf-8', errors='ignore')
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Queue the task
        task = process_document.apply_async(
            args=[document_content, file.filename, case_id],
            task_id=job_id
        )
        
        logger.info(f"Queued uploaded file processing: {job_id}")
        
        return ProcessCaseFileResponse(
            job_id=job_id,
            case_id=case_id,
            status="queued",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/{job_id}", response_model=JobStatusResponse)
async def get_job_results(job_id: str):
    """
    Get the status and results of a processing job
    
    Poll this endpoint to track job progress through stages:
    - PENDING: Job queued
    - PARSING: Analyzing document structure
    - EXTRACTING: Extracting facts
    - SYNTHESIZING: AI synthesis
    - ANALYZING: Contradiction detection
    - SUCCESS: Complete with results
    - FAILURE: Processing failed
    """
    try:
        # Get task result
        result = celery_app.AsyncResult(job_id)
        
        # Build response based on state
        if result.state == 'PENDING':
            return JobStatusResponse(
                job_id=job_id,
                state='PENDING',
                progress={
                    'current': 0,
                    'total': 4,
                    'status': 'Job is queued and waiting to start'
                },
                result=None,
                error=None
            )
        
        elif result.state == 'SUCCESS':
            return JobStatusResponse(
                job_id=job_id,
                state='SUCCESS',
                progress={
                    'current': 4,
                    'total': 4,
                    'status': 'Processing complete'
                },
                result=result.result,
                error=None
            )
        
        elif result.state == 'FAILURE':
            return JobStatusResponse(
                job_id=job_id,
                state='FAILURE',
                progress={
                    'current': 0,
                    'total': 4,
                    'status': 'Processing failed'
                },
                result=None,
                error={
                    'type': 'ProcessingError',
                    'message': str(result.info)
                }
            )
        
        else:
            # In progress states
            return JobStatusResponse(
                job_id=job_id,
                state=result.state,
                progress=result.info or {
                    'current': 1,
                    'total': 4,
                    'status': f'Processing: {result.state}'
                },
                result=None,
                error=None
            )
            
    except Exception as e:
        logger.error(f"Error getting job results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    try:
        celery_app.control.revoke(job_id, terminate=True)
        return {"message": f"Job {job_id} cancelled"}
    except Exception as e:
        logger.error(f"Error cancelling job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/active", response_model=List[Dict[str, Any]])
async def get_active_jobs():
    """Get list of active jobs"""
    try:
        i = celery_app.control.inspect()
        active = i.active()
        
        if not active:
            return []
        
        # Flatten active tasks from all workers
        all_tasks = []
        for worker, tasks in active.items():
            for task in tasks:
                all_tasks.append({
                    'job_id': task['id'],
                    'name': task['name'],
                    'worker': worker,
                    'args': task.get('args', [])
                })
        
        return all_tasks
        
    except Exception as e:
        logger.error(f"Error getting active jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Development/Demo endpoints
@app.post("/demo/process-sample")
async def process_sample_document():
    """Process a sample document for demonstration"""
    sample_doc = """
    CASE FILE: Johnson v. Smith Motors
    Date of Filing: 03/15/2024
    
    INCIDENT REPORT:
    On 01/10/2024, the plaintiff was involved in a motor vehicle accident.
    
    ---TABLE---
    
    Service: Emergency Room Visit
    Provider: Dr. Sarah Johnson, MD
    Date: 01/10/2024
    Amount: $3,450.00
    """
    
    request = ProcessCaseFileRequest(
        case_id="demo-001",
        document_name="sample_case.txt",
        document_content=sample_doc
    )
    
    return await process_case_file(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)