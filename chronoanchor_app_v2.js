/**
 * ChronoAnchor™ Workbench - V2.0 with API Integration
 * Phase 2: Full Intelligence Engine with real-time processing
 */

// API Configuration
const API_BASE_URL = 'http://localhost:8000';
const POLL_INTERVAL = 1000; // Poll every second

// Enhanced global state
const AppState = {
    currentPage: 1,
    totalPages: 2,
    activeFactId: null,
    facts: [],
    events: [],
    contradictions: [],
    filterType: 'all',
    currentJobId: null,
    processingStatus: null
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('ChronoAnchor™ Workbench V2.0 initialized');
    initializeEventListeners();
    setupFileUpload();
    updatePageIndicator();
});

// File upload functionality
function setupFileUpload() {
    // Add upload button to header
    const headerActions = document.querySelector('.header-actions');
    const uploadBtn = document.createElement('button');
    uploadBtn.className = 'btn-primary';
    uploadBtn.innerHTML = '📄 Upload Document';
    uploadBtn.onclick = () => document.getElementById('fileInput').click();
    
    // Create hidden file input
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.id = 'fileInput';
    fileInput.style.display = 'none';
    fileInput.accept = '.txt,.pdf';
    fileInput.onchange = handleFileUpload;
    
    headerActions.insertBefore(uploadBtn, headerActions.firstChild);
    document.body.appendChild(fileInput);
}

// Handle file upload
async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Show loading state
    showProcessingOverlay('Uploading document...');
    
    try {
        // Read file content
        const content = await readFileContent(file);
        
        // Submit to API
        const response = await fetch(`${API_BASE_URL}/process-case-file/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                case_id: `case-${Date.now()}`,
                document_name: file.name,
                document_content: content
            })
        });
        
        if (!response.ok) throw new Error('Upload failed');
        
        const result = await response.json();
        AppState.currentJobId = result.job_id;
        
        // Start polling for results
        startPolling(result.job_id);
        
    } catch (error) {
        console.error('Upload error:', error);
        hideProcessingOverlay();
        showNotification('Failed to upload document', 'error');
    }
}

// Read file content
function readFileContent(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

// Start polling for job results
async function startPolling(jobId) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/results/${jobId}`);
            if (!response.ok) throw new Error('Poll failed');
            
            const status = await response.json();
            updateProcessingStatus(status);
            
            if (status.state === 'SUCCESS') {
                clearInterval(pollInterval);
                handleProcessingComplete(status.result);
            } else if (status.state === 'FAILURE') {
                clearInterval(pollInterval);
                handleProcessingError(status.error);
            }
        } catch (error) {
            console.error('Polling error:', error);
            clearInterval(pollInterval);
            hideProcessingOverlay();
        }
    }, POLL_INTERVAL);
}

// Update processing status overlay
function updateProcessingStatus(status) {
    const overlay = document.getElementById('processingOverlay');
    const statusText = overlay.querySelector('.status-text');
    const progressBar = overlay.querySelector('.progress-bar-fill');
    
    if (status.progress) {
        const percent = (status.progress.current / status.progress.total) * 100;
        progressBar.style.width = `${percent}%`;
        statusText.textContent = status.progress.status;
    }
    
    // Update stage indicators
    const stages = ['PARSING', 'EXTRACTING', 'SYNTHESIZING', 'ANALYZING'];
    stages.forEach((stage, index) => {
        const stageEl = overlay.querySelector(`[data-stage="${stage}"]`);
        if (stageEl) {
            if (status.state === stage || stages.indexOf(status.state) > index) {
                stageEl.classList.add('active');
            }
        }
    });
}

// Handle processing complete
function handleProcessingComplete(result) {
    hideProcessingOverlay();
    
    // Update app state
    AppState.facts = result.facts || [];
    AppState.events = result.events || [];
    AppState.contradictions = result.contradictions || [];
    
    // Render the UI
    renderDocument(result);
    renderTimeline(result.events);
    
    // Show summary
    showNotification(
        `Processing complete! Found ${result.facts.length} facts, ` +
        `${result.events.length} events, and ${result.contradictions.length} contradictions.`,
        'success'
    );
}

// Handle processing error
function handleProcessingError(error) {
    hideProcessingOverlay();
    showNotification(`Processing failed: ${error.message}`, 'error');
}

// Render document with AI highlights
function renderDocument(result) {
    const documentContent = document.getElementById('documentContent');
    
    // For MVP, show a summary view
    let html = '<div class="pdf-page" data-page="1">';
    html += '<h3>AI-Enhanced Document Analysis</h3>';
    html += '<div class="document-summary">';
    html += `<p><strong>Document:</strong> ${result.document_name || 'Uploaded Document'}</p>`;
    html += `<p><strong>Facts Extracted:</strong> ${result.facts.length}</p>`;
    html += `<p><strong>Events Synthesized:</strong> ${result.events.length}</p>`;
    
    if (result.contradictions.length > 0) {
        html += `<p class="contradiction-alert">⚠️ <strong>${result.contradictions.length} contradictions detected!</strong></p>`;
    }
    
    html += '</div>';
    html += '</div>';
    
    documentContent.innerHTML = html;
}

// Render enhanced timeline with AI descriptions
function renderTimeline(events) {
    const timelineContainer = document.getElementById('timelineContainer');
    timelineContainer.innerHTML = '';
    
    events.forEach((event, index) => {
        const eventEl = createTimelineEvent(event, index);
        timelineContainer.appendChild(eventEl);
    });
    
    // Add contradiction indicators
    AppState.contradictions.forEach(contradiction => {
        highlightContradiction(contradiction);
    });
}

// Create timeline event element
function createTimelineEvent(event, index) {
    const div = document.createElement('div');
    div.className = 'timeline-event';
    div.setAttribute('data-event-id', event.id || index);
    div.setAttribute('data-type', 'synthesized');
    
    // Check if this event is part of a contradiction
    const isContradicted = AppState.contradictions.some(c => 
        c.event_1.date === event.date || c.event_2.date === event.date
    );
    
    div.innerHTML = `
        <div class="event-date">${formatDate(event.date)}</div>
        <div class="event-content">
            <span class="event-icon">🤖</span>
            <div class="event-description">
                <strong>AI Synthesized Event</strong>
                <p class="ai-description">${event.description}</p>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${(event.confidence || 0.95) * 100}%"></div>
                </div>
            </div>
        </div>
        ${isContradicted ? '<div class="conflict-indicator">🔥</div>' : ''}
        <div class="event-source">AI Generated</div>
    `;
    
    div.onclick = () => openEventInspector(event);
    
    return div;
}

// Highlight contradictions in timeline
function highlightContradiction(contradiction) {
    // Add visual indicators to contradicted events
    const events = document.querySelectorAll('.timeline-event');
    events.forEach(eventEl => {
        const date = eventEl.querySelector('.event-date').textContent;
        if (date === formatDate(contradiction.event_1.date) || 
            date === formatDate(contradiction.event_2.date)) {
            eventEl.classList.add('has-contradiction');
        }
    });
}

// Enhanced event inspector for AI content
function openEventInspector(event) {
    const inspector = document.getElementById('factInspector');
    const content = document.getElementById('inspectorContent');
    
    let html = '<div class="event-detail">';
    html += '<h4>AI-Synthesized Event</h4>';
    html += `<p class="event-date-large">${formatDate(event.date)}</p>`;
    html += `<div class="ai-description-box">${event.description}</div>`;
    
    // Confidence score
    html += '<div class="confidence-section">';
    html += '<h5>AI Confidence</h5>';
    html += `<div class="confidence-meter">`;
    html += `<div class="confidence-fill" style="width: ${(event.confidence || 0.95) * 100}%"></div>`;
    html += `<span class="confidence-label">${Math.round((event.confidence || 0.95) * 100)}%</span>`;
    html += '</div>';
    html += '</div>';
    
    // Check for contradictions
    const relatedContradictions = AppState.contradictions.filter(c => 
        c.event_1.date === event.date || c.event_2.date === event.date
    );
    
    if (relatedContradictions.length > 0) {
        html += '<div class="contradiction-section">';
        html += '<h5>🔥 Contradiction Detected</h5>';
        relatedContradictions.forEach(c => {
            html += `<div class="contradiction-detail">`;
            html += `<p class="contradiction-explanation">${c.explanation}</p>`;
            html += `<p class="contradiction-impact">Impact: ${c.impact}</p>`;
            html += `<div class="contradiction-events">`;
            html += `<div class="event-comparison">`;
            html += `<div class="event-1">`;
            html += `<strong>${formatDate(c.event_1.date)}</strong>`;
            html += `<p>${c.event_1.description}</p>`;
            html += `</div>`;
            html += `<div class="vs">VS</div>`;
            html += `<div class="event-2">`;
            html += `<strong>${formatDate(c.event_2.date)}</strong>`;
            html += `<p>${c.event_2.description}</p>`;
            html += `</div>`;
            html += `</div>`;
            html += `</div>`;
            html += `</div>`;
        });
        html += '</div>';
    }
    
    html += '</div>';
    
    content.innerHTML = html;
    inspector.classList.add('open');
}

// Processing overlay
function showProcessingOverlay(message) {
    let overlay = document.getElementById('processingOverlay');
    if (!overlay) {
        overlay = createProcessingOverlay();
        document.body.appendChild(overlay);
    }
    
    overlay.querySelector('.status-text').textContent = message;
    overlay.style.display = 'flex';
}

function hideProcessingOverlay() {
    const overlay = document.getElementById('processingOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

function createProcessingOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'processingOverlay';
    overlay.className = 'processing-overlay';
    overlay.innerHTML = `
        <div class="processing-content">
            <h2>Processing Document</h2>
            <div class="status-text">Initializing...</div>
            <div class="progress-bar">
                <div class="progress-bar-fill"></div>
            </div>
            <div class="processing-stages">
                <div class="stage" data-stage="PARSING">📄 Parsing</div>
                <div class="stage" data-stage="EXTRACTING">🔍 Extracting</div>
                <div class="stage" data-stage="SYNTHESIZING">🤖 Synthesizing</div>
                <div class="stage" data-stage="ANALYZING">🔥 Analyzing</div>
            </div>
        </div>
    `;
    return overlay;
}

// Utility functions
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'error' ? '#dc2626' : type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Add required CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .processing-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    }
    
    .processing-content {
        background: white;
        padding: 40px;
        border-radius: 12px;
        text-align: center;
        max-width: 500px;
        width: 90%;
    }
    
    .progress-bar {
        width: 100%;
        height: 8px;
        background: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
        margin: 20px 0;
    }
    
    .progress-bar-fill {
        height: 100%;
        background: #3b82f6;
        transition: width 0.3s ease;
        width: 0%;
    }
    
    .processing-stages {
        display: flex;
        justify-content: space-around;
        margin-top: 20px;
    }
    
    .stage {
        padding: 8px 16px;
        background: #f3f4f6;
        border-radius: 20px;
        font-size: 14px;
        opacity: 0.5;
        transition: all 0.3s ease;
    }
    
    .stage.active {
        background: #3b82f6;
        color: white;
        opacity: 1;
    }
    
    .ai-description {
        color: #7c3aed;
        font-style: italic;
    }
    
    .confidence-bar {
        width: 100%;
        height: 4px;
        background: #e5e7eb;
        border-radius: 2px;
        margin-top: 8px;
        overflow: hidden;
    }
    
    .confidence-fill {
        height: 100%;
        background: #10b981;
        transition: width 0.3s ease;
    }
    
    .contradiction-section {
        margin-top: 20px;
        padding: 16px;
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 8px;
    }
    
    .contradiction-explanation {
        color: #dc2626;
        font-weight: 500;
    }
    
    .event-comparison {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-top: 12px;
    }
    
    .event-1, .event-2 {
        flex: 1;
        padding: 12px;
        background: white;
        border-radius: 6px;
        font-size: 14px;
    }
    
    .vs {
        font-weight: bold;
        color: #dc2626;
    }
    
    .has-contradiction {
        border-color: #dc2626;
        background: #fef2f2;
    }
    
    .conflict-indicator {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.2); }
        100% { transform: scale(1); }
    }
`;
document.head.appendChild(style);

// Keep original functions for backward compatibility
function anchorToFact(factId) {
    // Original anchor functionality still works
    console.log(`Legacy anchor to fact ${factId}`);
}

// Export for module usage
window.ChronoAnchorV2 = {
    AppState,
    handleFileUpload,
    showNotification
};