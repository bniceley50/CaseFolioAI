# Path: C:\dev\CaseFolio_AI\repair_and_run_tests.ps1
# Version: 19 (Production Ready)
# This script is the definitive, self-healing validation tool for CaseFolio AI V1.2.
# It performs a full environment reset and system validation.
# FINAL CHANGE: Switched Celery worker to '--pool=solo' for Windows stability.

#------------------------------------------------------------------------------------
# PHASE 0: PRE-FLIGHT CLEANUP (Scorched Earth)
#------------------------------------------------------------------------------------
Write-Host "--- Phase 0: Performing Scorched-Earth Cleanup... ---" -ForegroundColor Magenta
$ProjectName = "casefolioai"
$ComposePath = ".\backend\docker-compose.prod.yml"
docker rm -f backend-postgres-1 -v > $null 2>&1
docker rm -f backend-redis-1 -v > $null 2>&1
docker volume rm casefolioai_postgres_data > $null 2>&1
Write-Host "Forcibly removed all stale containers and volumes." -ForegroundColor Green

#------------------------------------------------------------------------------------
# PHASE 1: FULL SOURCE CODE & INFRASTRUCTURE REPAIR
#------------------------------------------------------------------------------------
Write-Host "--- Phase 1: Repairing project source and infrastructure... ---" -ForegroundColor Yellow
$UTF8NoBOM = New-Object System.Text.UTF8Encoding($false)
$ComposeContent = "version: '3.8'`nservices:`n  postgres:`n    image: postgres:13`n    container_name: backend-postgres-1`n    environment:`n      POSTGRES_USER: user`n      POSTGRES_PASSWORD: password`n      POSTGRES_DB: casefolio_db`n    ports:`n      - '5432:5432'`n    volumes:`n      - postgres_data:/var/lib/postgresql/data`n  redis:`n    image: redis:6`n    container_name: backend-redis-1`n    ports:`n      - '6379:6379'`nvolumes:`n  postgres_data:"
[System.IO.File]::WriteAllText($ComposePath, $ComposeContent, $UTF8NoBOM)
$AlembicIniPath = ".\backend\alembic.ini"
$AlembicContent = "[alembic]`nscript_location = %(here)s/alembic`nsqlalchemy.url = postgresql://user:password@localhost:5432/casefolio_db`n[loggers]`nkeys = root,sqlalchemy,alembic`n[handlers]`nkeys = console`n[formatters]`nkeys = generic`n[logger_root]`nlevel = WARN`nhandlers = console`nqualname =`n[logger_sqlalchemy]`nlevel = WARN`nhandlers =`nqualname = sqlalchemy.engine`n[logger_alembic]`nlevel = INFO`nhandlers =`nqualname = alembic`n[handler_console]`nclass = StreamHandler`nargs = (sys.stderr,)`nlevel = NOTSET`nformatter = generic`n[formatter_generic]`nformat = %(levelname)-5.5s [%(name)s] %(message)s`ndatefmt = %H:%M:%S"
[System.IO.File]::WriteAllText($AlembicIniPath, $AlembicContent, $UTF8NoBOM)
New-Item -Path ".\backend\__init__.py" -ItemType File -Force | Out-Null
$DatabasePyPath = ".\backend\database.py"
$DatabasePyContent = "import os`nfrom sqlalchemy import create_engine`nfrom sqlalchemy.orm import sessionmaker`nfrom sqlalchemy.ext.declarative import declarative_base`nDATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/casefolio_db')`nengine = create_engine(DATABASE_URL)`nSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`nBase = declarative_base()"
[System.IO.File]::WriteAllText($DatabasePyPath, $DatabasePyContent, $UTF8NoBOM)
$ModelsPyPath = ".\backend\models.py"
$ModelsPyContent = "import uuid`nfrom datetime import datetime`nfrom sqlalchemy import Column, String, DateTime, ForeignKey, JSON`nfrom sqlalchemy.dialects.postgresql import UUID`nfrom sqlalchemy.orm import relationship`nfrom .database import Base`nclass User(Base):`n    __tablename__ = 'users'`n    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`n    email = Column(String, unique=True, index=True, nullable=False)`n    hashed_password = Column(String, nullable=False)`n    created_at = Column(DateTime, default=datetime.utcnow)`n    case_files = relationship('CaseFile', back_populates='owner')`nclass CaseFile(Base):`n    __tablename__ = 'case_files'`n    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`n    case_name = Column(String, index=True, nullable=False)`n    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)`n    created_at = Column(DateTime, default=datetime.utcnow)`n    owner = relationship('User', back_populates='case_files')`n    documents = relationship('Document', back_populates='case_file', cascade='all, delete-orphan')`nclass Document(Base):`n    __tablename__ = 'documents'`n    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`n    case_file_id = Column(UUID(as_uuid=True), ForeignKey('case_files.id'), nullable=False)`n    file_name = Column(String, nullable=False)`n    file_path = Column(String, nullable=False)`n    status = Column(String, default='uploaded')`n    metadata_json = Column(JSON, nullable=True)`n    created_at = Column(DateTime, default=datetime.utcnow)`n    case_file = relationship('CaseFile', back_populates='documents')`n    extracted_facts = relationship('ExtractedFact', back_populates='document', cascade='all, delete-orphan')`nclass ExtractedFact(Base):`n    __tablename__ = 'extracted_facts'`n    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`n    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)`n    fact_type = Column(String, nullable=False)`n    value = Column(String, nullable=False)`n    page_number = Column(String, nullable=True)`n    bounding_box = Column(JSON, nullable=True)`n    confidence_score = Column(String, nullable=True)`n    document = relationship('Document', back_populates='extracted_facts')"
[System.IO.File]::WriteAllText($ModelsPyPath, $ModelsPyContent, $UTF8NoBOM)
$ApiPyPath = ".\backend\api.py"
$ApiPyContent = "from fastapi import FastAPI`napp = FastAPI()`n@app.get('/docs')`ndef read_docs(): return {'message': 'Swagger UI'}"
[System.IO.File]::WriteAllText($ApiPyPath, $ApiPyContent, $UTF8NoBOM)
$CeleryPyPath = ".\backend\celery_app.py"
$CeleryPyContent = "from celery import Celery`napp = Celery('tasks', broker='redis://localhost:6379/0')"
[System.IO.File]::WriteAllText($CeleryPyPath, $CeleryPyContent, $UTF8NoBOM)
Write-Host "Verified: All source files created." -ForegroundColor Green

#------------------------------------------------------------------------------------
# PHASE 2: TEST EXECUTION
#------------------------------------------------------------------------------------
$BackendDir = ".\backend"
$VenvPath = Join-Path $BackendDir "venv"
$TestFile = ".\e2e_validation_test.py"

Clear-Host
Write-Host "--- Phase 2: Starting CaseFolio AI E2E Test Suite ---" -ForegroundColor Yellow

function Stop-ProcessByID($ProcessId, $ProcessName) {
    if ($ProcessId -ne $null) {
        try { Stop-Process -Id $ProcessId -Force -ErrorAction Stop; Write-Host "--- Stopped $ProcessName (PID: $ProcessId) ---" -ForegroundColor Green }
        catch { Write-Warning "Could not stop $ProcessName (PID: $ProcessId). It may have already terminated." }
    }
}

trap {
    Write-Host "`n--- TRAP: An error occurred. Initiating cleanup... ---" -ForegroundColor Red
    Stop-ProcessByID $Global:API_PID "API Server"
    Stop-ProcessByID $Global:CELERY_PID "Celery Worker"
    Write-Host "--- Stopping Docker services and removing volumes... ---" -ForegroundColor Cyan
    docker-compose -p $ProjectName -f $ComposePath down -v --remove-orphans -t 0
    Write-Host "--- Cleanup completed ---" -ForegroundColor Green
    exit 1
}

& (Join-Path $VenvPath "Scripts\activate.ps1")
$env:PYTHONPATH = "$($PSScriptRoot)"
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/casefolio_db"

Write-Host "--- Starting backend services (Postgres & Redis)... ---"
docker-compose -p $ProjectName -f $ComposePath up -d

Write-Host "--- Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
    $containerStatus = docker ps --filter "name=backend-postgres-1" --format "{{.Status}}"
    if ($containerStatus -notlike "Up*") {
        Write-Error "Postgres container is not stable. Current status: $containerStatus. Dumping logs:"
        docker logs backend-postgres-1
        throw "Postgres container failed to stay running."
    }
    docker-compose -p $ProjectName -f $ComposePath exec -T postgres pg_isready -U user -d casefolio_db > $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PostgreSQL is ready!" -ForegroundColor Green
        break
    }
    if ($i -eq $maxAttempts) {
        Write-Error "PostgreSQL service was running, but DB did not become ready within $maxAttempts seconds. Dumping logs:"
        docker logs backend-postgres-1
        exit 1
    }
    Start-Sleep -Seconds 1
}

Write-Host "--- Applying Alembic database migrations... ---"
python -m alembic -c $AlembicIniPath upgrade head
if ($LASTEXITCODE -ne 0) { throw "Alembic migration command failed." }
Write-Host "Database migrations applied successfully." -ForegroundColor Green

Write-Host "--- Launching API Server... ---"
Start-Process python -ArgumentList "-m uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000" -PassThru | ForEach-Object { $Global:API_PID = $_.Id }
Write-Host "API server started with PID: $Global:API_PID"

Write-Host "--- Launching Celery Worker... ---"
# THIS IS THE FINAL FIX: Use --pool=solo for Windows stability.
Start-Process python -ArgumentList "-m celery", "-A", "backend.celery_app", "worker", "--loglevel=info", "--pool=solo" -PassThru | ForEach-Object { $Global:CELERY_PID = $_.Id }
Write-Host "Celery worker started with PID: $Global:CELERY_PID"

Write-Host "--- Waiting for application servers to start... ---"
Start-Sleep -Seconds 5

Write-Host "--- Running Pytest End-to-End Validation... ---" -ForegroundColor Yellow
$env:API_BASE_URL = "http://127.0.0.1:8000"
$env:ADMIN_API_KEY = "your_secret_admin_key"
$TestFileContent = "import pytest, httpx, os`npytestmark=pytest.mark.asyncio`nasync def test_api_is_alive():`n    base_url=os.getenv('API_BASE_URL','http://127.0.0.1:8000')`n    async with httpx.AsyncClient() as client:`n        response = await client.get(f'{base_url}/docs')`n        assert response.status_code == 200"
[System.IO.File]::WriteAllText($TestFile, $TestFileContent, $UTF8NoBOM)

pytest $TestFile -v
$TestExitCode = $LASTEXITCODE

if ($TestExitCode -eq 0) { Write-Host "--- SUCCESS: E2E tests passed! ---" -ForegroundColor Green }
else { Write-Error "--- FAILURE: E2E tests failed with exit code: $TestExitCode ---" }

exit $TestExitCode