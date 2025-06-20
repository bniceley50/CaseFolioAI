# CaseFolio AI - Intelligence Engine V1.0

AI-powered legal document analysis platform with ChronoAnchor™ Workbench interface.

## Features

- **Trust Engine**: Deterministic extraction of dates, names, and monetary amounts
- **Intelligence Engine**: AI-powered event synthesis using GPT-3.5-turbo
- **Contradiction Detection**: Hybrid rule-based + GPT-4 analysis
- **ChronoAnchor™ Workbench**: Evidence-locked UI with <300ms Click-to-Anchor response
- **Asynchronous Processing**: Celery-based scalable architecture

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend UI   │────▶│   FastAPI       │────▶│   Celery        │
│  (ChronoAnchor) │     │   Endpoints     │     │   Workers       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │   LLM APIs      │
                                                 │  (OpenAI)       │
                                                 └─────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your OpenAI API key and Redis configuration
```

### 3. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally
redis-server
```

### 4. Start Celery Worker

```bash
celery -A celery_app worker --loglevel=info
```

### 5. Start API Server

```bash
uvicorn api:app --reload
```

### 6. Open UI

Open `chronoanchor_workbench.html` in a modern web browser.

## Usage

1. **Upload Document**: Click "📄 Upload Document" in the UI
2. **Monitor Processing**: Watch real-time progress through stages:
   - PARSING: Document structure analysis
   - EXTRACTING: Fact extraction
   - SYNTHESIZING: AI event generation
   - ANALYZING: Contradiction detection
3. **Review Results**: 
   - Timeline shows AI-synthesized events
   - 🔥 indicators highlight contradictions
   - Click events for detailed analysis

## API Endpoints

- `POST /process-case-file/`: Submit document for processing
- `GET /results/{job_id}`: Poll for job status and results
- `GET /health`: Check system health

## Development

### Running Tests

```bash
# Test extraction pipeline
python trust_engine_mvp_sprint2.py

# Test AI synthesis (mock mode)
python intelligence_engine_phase2.py
```

### Project Structure

```
CaseFolio_AI/
├── api.py                    # FastAPI application
├── celery_app.py            # Celery configuration
├── tasks.py                 # Async task definitions
├── event_synthesizer.py     # GPT-3.5 synthesis
├── contradiction_analyzer.py # GPT-4 contradiction detection
├── chronoanchor_workbench.html # UI
├── chronoanchor_app_v2.js   # Enhanced UI logic
└── trust_engine_mvp_sprint2.py # Core extraction engine
```

## Cost Optimization

- **Tiered LLM Usage**:
  - GPT-3.5-turbo: High-volume event synthesis (~$0.001 per event)
  - GPT-4: High-value contradiction analysis (~$0.03 per analysis)
- **Token Limiting**: Max 100 tokens for synthesis, 200 for analysis
- **Caching**: Results cached for 1 hour

## Security Notes

- Never commit `.env` file with real API keys
- Use environment-specific Redis passwords
- Implement rate limiting in production
- Sanitize user inputs before processing

## Future Enhancements (Phase 3)

- Custom extraction rules studio
- Clio/MyCase integrations
- Advanced analytics dashboard
- Automated report generation

## Support

For issues or questions, contact the CaseFolio AI development team.#   C a s e F o l i o A I  
 