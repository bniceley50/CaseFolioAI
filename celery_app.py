"""
CaseFolio AI - Celery Configuration
Asynchronous task processing for scalable document analysis
"""

from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery instance
app = Celery(
    'casefolio',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks']
)

# Celery configuration
app.conf.update(
    # Task configuration
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Performance tuning
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task routing
    task_routes={
        'tasks.process_document': {'queue': 'document_processing'},
        'tasks.synthesize_events': {'queue': 'ai_synthesis'},
        'tasks.analyze_contradictions': {'queue': 'ai_analysis'}
    },
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True
)

# Task state definitions
class TaskStates:
    PENDING = 'PENDING'
    PARSING = 'PARSING'
    EXTRACTING = 'EXTRACTING'
    SYNTHESIZING = 'SYNTHESIZING'
    ANALYZING = 'ANALYZING'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'

# Celery beat schedule (for future scheduled tasks)
app.conf.beat_schedule = {
    # Example: Clean up old results every hour
    'cleanup-old-results': {
        'task': 'tasks.cleanup_old_results',
        'schedule': 3600.0,  # Every hour
    },
}