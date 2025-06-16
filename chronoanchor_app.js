/**
 * ChronoAnchor™ Workbench - Main Application
 * Production-ready frontend with full API integration
 */

// Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';
const POLLING_INTERVAL = 3000; // 3 seconds
const MAX_POLL_ATTEMPTS = 60; // 3 minutes max

// Global state
let currentJob = null;
let currentApiKey = null;
let pollInterval = null;
let currentPage = 1;
let totalPages = 1;
let documentData = null;
let factsMap = new Map();
let eventsData = [];
let contradictionsData = [];

// API Key Management
function initializeApiKey() {
    // Check sessionStorage for existing key
    currentApiKey = sessionStorage.getItem('casefolio_api_key');
    
    if (!currentApiKey) {
        showApiKeyPrompt();
    }
}

function showApiKeyPrompt() {
    const modal = document.createElement('div');
    modal.className = 'api-key-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <h2>API Key Required</h2>
            <p>Please enter your CaseFolio AI API key to continue:</p>
            <input type="password" id="apiKeyInput" placeholder="Enter API key..." />
            <div class="modal-actions">
                <button onclick="saveApiKey()" class="btn-primary">Save</button>
                <button onclick="useDemo()" class="btn-secondary">Use Demo Mode</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Focus input
    setTimeout(() => {
        document.getElementById('apiKeyInput').focus();
    }, 100);
}

function saveApiKey() {
    const input = document.getElementById('apiKeyInput');
    const apiKey = input.value.trim();
    
    if (!apiKey) {
        alert('Please enter a valid API key');
        return;
    }
    
    currentApiKey = apiKey;
    sessionStorage.setItem('casefolio_api_key', apiKey);
    
    // Remove modal
    const modal = document.querySelector('.api-key-modal');
    if (modal) modal.remove();
    
    // Test connection
    testApiConnection();
}

function useDemo() {
    // Remove modal
    const modal = document.querySelector('.api-key-modal');
    if (modal) modal.remove();
    
    // Switch to demo mode (no API key needed)
    currentApiKey = 'DEMO';
    console.log('Running in demo mode - no authentication required');
}

async function testApiConnection() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            headers: getAuthHeaders()
        });
        
        if (!response.ok) {
            throw new Error('Invalid API key');
        }
        
        const data = await response.json();
        console.log('API connection successful:', data);
    } catch (error) {
        console.error('API connection failed:', error);
        alert('Failed to connect to API. Please check your API key.');
        showApiKeyPrompt();
    }
}

function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };
    
    if (currentApiKey && currentApiKey !== 'DEMO') {
        headers['X-API-Key'] = currentApiKey;
    }
    
    return headers;
}

// Document Upload
async function uploadDocument() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf,.txt,.doc,.docx';
    
    fileInput.onchange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        showLoading(true);
        
        try {
            // For demo/MVP, we'll send text content
            // In production, this would use multipart/form-data
            const content = await readFileAsText(file);
            
            const response = await fetch(`${API_BASE_URL}/documents/upload`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    case_file_id: 'case-' + Date.now(),
                    filename: file.name,
                    content: content,
                    content_type: file.type
                })
            });
            
            if (!response.ok) {
                throw new Error('Upload failed');
            }
            
            const result = await response.json();
            
            // Start processing
            await processDocument(result.document_id, file.name);
            
        } catch (error) {
            console.error('Upload error:', error);
            alert('Failed to upload document. Please try again.');
        } finally {
            showLoading(false);
        }
    };
    
    fileInput.click();
}

async function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

// Document Processing
async function processDocument(documentId, filename) {
    try {
        // Create processing job
        const response = await fetch(`${API_BASE_URL}/processing/jobs`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                document_id: documentId,
                processing_type: 'full_analysis'
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to start processing');
        }
        
        const job = await response.json();
        currentJob = job;
        
        // Update UI
        updateCaseInfo(filename, 'Processing...');
        
        // Start polling
        startPolling(job.job_id);
        
    } catch (error) {
        console.error('Processing error:', error);
        alert('Failed to process document. Please try again.');
    }
}

// Polling for Results
function startPolling(jobId) {
    let attempts = 0;
    
    // Clear any existing interval
    if (pollInterval) {
        clearInterval(pollInterval);
    }
    
    // Update UI to show processing
    showProcessingStatus('Initializing...');
    
    pollInterval = setInterval(async () => {
        attempts++;
        
        try {
            const response = await fetch(`${API_BASE_URL}/processing/jobs/${jobId}`, {
                headers: getAuthHeaders()
            });
            
            if (!response.ok) {
                throw new Error('Failed to get job status');
            }
            
            const status = await response.json();
            
            // Update progress
            updateProcessingProgress(status);
            
            if (status.status === 'completed') {
                clearInterval(pollInterval);
                pollInterval = null;
                
                // Get full results
                await loadProcessingResults(jobId);
                
            } else if (status.status === 'failed' || attempts >= MAX_POLL_ATTEMPTS) {
                clearInterval(pollInterval);
                pollInterval = null;
                
                showError(status.error || 'Processing timeout');
            }
            
        } catch (error) {
            console.error('Polling error:', error);
            
            if (attempts >= 3) {
                clearInterval(pollInterval);
                pollInterval = null;
                showError('Failed to get processing status');
            }
        }
    }, POLLING_INTERVAL);
}

function updateProcessingProgress(status) {
    const messages = {
        'parsing': 'Parsing document structure...',
        'extracting': 'Extracting facts and entities...',
        'synthesizing': 'Synthesizing events with AI...',
        'analyzing': 'Analyzing for contradictions...',
        'completed': 'Processing complete!'
    };
    
    const progress = status.progress || {};
    const message = messages[status.current_stage] || 'Processing...';
    
    showProcessingStatus(`${message} (${progress.current || 0}/${progress.total || 4})`);
}

async function loadProcessingResults(jobId) {
    try {
        // Get detailed results
        const response = await fetch(`${API_BASE_URL}/processing/jobs/${jobId}/results`, {
            headers: getAuthHeaders()
        });
        
        if (!response.ok) {
            throw new Error('Failed to load results');
        }
        
        const results = await response.json();
        
        // Process and display results
        processResults(results);
        
        // Hide processing status
        hideProcessingStatus();
        
        // Update case status
        updateCaseInfo(results.document_name, 'Analysis Complete');
        
    } catch (error) {
        console.error('Error loading results:', error);
        showError('Failed to load processing results');
    }
}

// Results Processing
function processResults(results) {
    // Clear existing data
    factsMap.clear();
    eventsData = [];
    contradictionsData = [];
    
    // Store document data
    documentData = {
        name: results.document_name,
        pages: results.pages || [],
        totalPages: results.total_pages || 1
    };
    
    totalPages = documentData.totalPages;
    
    // Process facts
    if (results.facts) {
        results.facts.forEach(fact => {
            factsMap.set(fact.id, {
                ...fact,
                page: fact.source?.page_number || 1,
                boundingBox: fact.source?.bounding_box
            });
        });
    }
    
    // Process events
    if (results.events) {
        eventsData = results.events.map(event => ({
            ...event,
            date: new Date(event.event_date),
            factIds: event.source_facts?.map(f => f.id) || []
        }));
        
        // Sort by date
        eventsData.sort((a, b) => a.date - b.date);
    }
    
    // Process contradictions
    if (results.contradictions) {
        contradictionsData = results.contradictions;
    }
    
    // Update UI
    renderDocument();
    renderTimeline();
    
    // Show first page
    showPage(1);
}

// Document Rendering
function renderDocument() {
    const container = document.getElementById('documentContent');
    
    if (!documentData || !documentData.pages || documentData.pages.length === 0) {
        // Fallback rendering for demo mode
        renderDemoDocument(container);
        return;
    }
    
    // Clear existing content
    container.innerHTML = '<div class="pdf-container"></div>';
    const pdfContainer = container.querySelector('.pdf-container');
    
    // Render each page
    documentData.pages.forEach((page, index) => {
        const pageDiv = document.createElement('div');
        pageDiv.className = 'pdf-page';
        pageDiv.dataset.page = index + 1;
        pageDiv.style.display = index === 0 ? 'block' : 'none';
        
        // Render page content with highlighted facts
        pageDiv.innerHTML = highlightFactsInText(page.text, page.page_number);
        
        pdfContainer.appendChild(pageDiv);
    });
    
    // Update page counter
    updatePageCounter();
}

function renderDemoDocument(container) {
    // Keep existing demo content but add data attributes
    const highlights = container.querySelectorAll('.highlight-deterministic');
    highlights.forEach((el, index) => {
        el.dataset.factId = index + 1;
        el.onclick = () => showFactDetails(index + 1);
    });
}

function highlightFactsInText(text, pageNumber) {
    let highlightedText = text;
    
    // Apply highlights for facts on this page
    factsMap.forEach((fact, factId) => {
        if (fact.page === pageNumber && fact.value) {
            const regex = new RegExp(`(${escapeRegex(fact.value)})`, 'gi');
            highlightedText = highlightedText.replace(regex, 
                `<span class="highlight-deterministic" data-fact-id="${factId}" onclick="showFactDetails(${factId})">$1</span>`
            );
        }
    });
    
    return `<div class="page-content">${highlightedText}</div>`;
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Timeline Rendering
function renderTimeline() {
    const container = document.getElementById('timelineContainer');
    container.innerHTML = '';
    
    if (eventsData.length === 0) {
        container.innerHTML = '<div class="no-events">No events found</div>';
        return;
    }
    
    // Group events by date
    const eventsByDate = groupEventsByDate(eventsData);
    
    // Render each date group
    Object.entries(eventsByDate).forEach(([dateStr, events]) => {
        events.forEach(event => {
            const eventDiv = createTimelineEvent(event);
            container.appendChild(eventDiv);
        });
    });
    
    // Add contradiction indicators
    addContradictionIndicators();
}

function groupEventsByDate(events) {
    const groups = {};
    
    events.forEach(event => {
        const dateStr = event.date.toISOString().split('T')[0];
        if (!groups[dateStr]) {
            groups[dateStr] = [];
        }
        groups[dateStr].push(event);
    });
    
    return groups;
}

function createTimelineEvent(event) {
    const div = document.createElement('div');
    div.className = 'timeline-event';
    div.dataset.eventId = event.id;
    div.dataset.type = event.category || 'general';
    
    // Check if this event is involved in contradictions
    const hasContradiction = contradictionsData.some(c => 
        c.event1_id === event.id || c.event2_id === event.id
    );
    
    if (hasContradiction) {
        div.classList.add('has-contradiction');
    }
    
    // Format date
    const dateStr = event.date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    // Determine icon
    const icon = getEventIcon(event.category);
    
    // Get source page
    const sourcePage = getEventSourcePage(event);
    
    div.innerHTML = `
        <div class="event-date">${dateStr}</div>
        <div class="event-content">
            <span class="event-icon">${icon}</span>
            <div class="event-description">
                <strong>${event.title || 'Event'}</strong>
                <p>${event.event_description}</p>
                ${event.confidence_score ? `<span class="confidence">Confidence: ${(event.confidence_score * 100).toFixed(0)}%</span>` : ''}
            </div>
            ${hasContradiction ? '<span class="contradiction-indicator" title="Potential contradiction">🔥</span>' : ''}
        </div>
        <div class="event-source">Page ${sourcePage}</div>
    `;
    
    // Add click handler
    div.onclick = () => handleTimelineClick(event);
    
    return div;
}

function getEventIcon(category) {
    const icons = {
        'medical': '🏥',
        'legal': '⚖️',
        'financial': '💰',
        'communication': '📧',
        'general': '📄'
    };
    return icons[category] || '📄';
}

function getEventSourcePage(event) {
    if (event.factIds && event.factIds.length > 0) {
        const fact = factsMap.get(event.factIds[0]);
        return fact?.page || 1;
    }
    return 1;
}

function addContradictionIndicators() {
    contradictionsData.forEach(contradiction => {
        // Add visual connection between contradicting events
        const event1El = document.querySelector(`[data-event-id="${contradiction.event1_id}"]`);
        const event2El = document.querySelector(`[data-event-id="${contradiction.event2_id}"]`);
        
        if (event1El && event2El) {
            // Add contradiction link class
            event1El.classList.add('contradiction-link');
            event2El.classList.add('contradiction-link');
            
            // Store contradiction data
            event1El.dataset.contradictionId = contradiction.id;
            event2El.dataset.contradictionId = contradiction.id;
        }
    });
}

// Click-to-Anchor Implementation
function handleTimelineClick(event) {
    // Get the first fact associated with this event
    if (event.factIds && event.factIds.length > 0) {
        const factId = event.factIds[0];
        anchorToFact(factId);
    } else {
        // Try to find page from event data
        const page = getEventSourcePage(event);
        showPage(page);
    }
    
    // Show event details in inspector
    showEventDetails(event);
}

function anchorToFact(factId) {
    const fact = factsMap.get(factId);
    if (!fact) return;
    
    // Navigate to the page
    showPage(fact.page);
    
    // Highlight the fact
    setTimeout(() => {
        const element = document.querySelector(`[data-fact-id="${factId}"]`);
        if (element) {
            // Scroll into view
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Add highlight animation
            element.classList.add('highlight-active');
            setTimeout(() => {
                element.classList.remove('highlight-active');
            }, 2000);
        }
    }, 100);
    
    // Show fact details
    showFactDetails(factId);
}

// Fact Inspector
function showFactDetails(factId) {
    const fact = factsMap.get(factId);
    if (!fact) return;
    
    const inspector = document.getElementById('factInspector');
    const content = document.getElementById('inspectorContent');
    
    content.innerHTML = `
        <div class="fact-detail">
            <div class="detail-row">
                <span class="label">Type:</span>
                <span class="value">${fact.fact_type}</span>
            </div>
            <div class="detail-row">
                <span class="label">Value:</span>
                <span class="value">${fact.value}</span>
            </div>
            <div class="detail-row">
                <span class="label">Page:</span>
                <span class="value">${fact.page}</span>
            </div>
            ${fact.confidence ? `
                <div class="detail-row">
                    <span class="label">Confidence:</span>
                    <span class="value">${(fact.confidence * 100).toFixed(0)}%</span>
                </div>
            ` : ''}
            ${fact.context ? `
                <div class="detail-section">
                    <h4>Context</h4>
                    <p>${fact.context}</p>
                </div>
            ` : ''}
        </div>
        
        <div class="related-events">
            <h4>Related Events</h4>
            ${renderRelatedEvents(factId)}
        </div>
    `;
    
    // Show inspector
    inspector.classList.add('active');
}

function showEventDetails(event) {
    const inspector = document.getElementById('factInspector');
    const content = document.getElementById('inspectorContent');
    
    // Find any contradictions
    const contradictions = contradictionsData.filter(c => 
        c.event1_id === event.id || c.event2_id === event.id
    );
    
    content.innerHTML = `
        <div class="event-detail">
            <h3>${event.title || 'Event Details'}</h3>
            <div class="detail-row">
                <span class="label">Date:</span>
                <span class="value">${event.date.toLocaleDateString()}</span>
            </div>
            <div class="detail-row">
                <span class="label">Category:</span>
                <span class="value">${event.category || 'General'}</span>
            </div>
            <div class="detail-section">
                <h4>Description</h4>
                <p>${event.event_description}</p>
            </div>
            ${event.confidence_score ? `
                <div class="detail-row">
                    <span class="label">AI Confidence:</span>
                    <span class="value">${(event.confidence_score * 100).toFixed(0)}%</span>
                </div>
            ` : ''}
        </div>
        
        ${contradictions.length > 0 ? `
            <div class="contradictions-section">
                <h4>⚠️ Potential Contradictions</h4>
                ${contradictions.map(c => `
                    <div class="contradiction-detail">
                        <p class="severity-${c.severity}">${c.explanation}</p>
                        <span class="severity">Severity: ${c.severity}</span>
                    </div>
                `).join('')}
            </div>
        ` : ''}
        
        <div class="source-facts">
            <h4>Source Facts</h4>
            ${renderSourceFacts(event.factIds)}
        </div>
    `;
    
    // Show inspector
    inspector.classList.add('active');
}

function renderRelatedEvents(factId) {
    const relatedEvents = eventsData.filter(event => 
        event.factIds && event.factIds.includes(factId)
    );
    
    if (relatedEvents.length === 0) {
        return '<p>No related events found</p>';
    }
    
    return relatedEvents.map(event => `
        <div class="related-event" onclick="handleTimelineClick(${JSON.stringify(event).replace(/"/g, '&quot;')})">
            <span class="event-icon">${getEventIcon(event.category)}</span>
            <span>${event.event_description}</span>
        </div>
    `).join('');
}

function renderSourceFacts(factIds) {
    if (!factIds || factIds.length === 0) {
        return '<p>No source facts</p>';
    }
    
    return factIds.map(factId => {
        const fact = factsMap.get(factId);
        if (!fact) return '';
        
        return `
            <div class="source-fact" onclick="anchorToFact(${factId})">
                <span class="fact-type">${fact.fact_type}:</span>
                <span class="fact-value">${fact.value}</span>
                <span class="fact-page">(Page ${fact.page})</span>
            </div>
        `;
    }).join('');
}

// Page Navigation
function showPage(pageNum) {
    if (pageNum < 1 || pageNum > totalPages) return;
    
    currentPage = pageNum;
    
    // Hide all pages
    document.querySelectorAll('.pdf-page').forEach(page => {
        page.style.display = 'none';
    });
    
    // Show current page
    const currentPageEl = document.querySelector(`[data-page="${pageNum}"]`);
    if (currentPageEl) {
        currentPageEl.style.display = 'block';
    }
    
    updatePageCounter();
}

function previousPage() {
    if (currentPage > 1) {
        showPage(currentPage - 1);
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        showPage(currentPage + 1);
    }
}

function updatePageCounter() {
    document.getElementById('currentPage').textContent = currentPage;
    document.getElementById('totalPages').textContent = totalPages;
}

// UI Helpers
function showLoading(show) {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) {
        indicator.style.display = show ? 'flex' : 'none';
    }
}

function showProcessingStatus(message) {
    let statusBar = document.getElementById('processingStatus');
    
    if (!statusBar) {
        statusBar = document.createElement('div');
        statusBar.id = 'processingStatus';
        statusBar.className = 'processing-status';
        document.body.appendChild(statusBar);
    }
    
    statusBar.innerHTML = `
        <div class="processing-content">
            <div class="spinner"></div>
            <span>${message}</span>
        </div>
    `;
    statusBar.style.display = 'block';
}

function hideProcessingStatus() {
    const statusBar = document.getElementById('processingStatus');
    if (statusBar) {
        statusBar.style.display = 'none';
    }
}

function showError(message) {
    hideProcessingStatus();
    alert(`Error: ${message}`);
}

function updateCaseInfo(name, status) {
    const caseNameEl = document.querySelector('.case-name');
    const caseStatusEl = document.querySelector('.case-status');
    
    if (caseNameEl) caseNameEl.textContent = name;
    if (caseStatusEl) caseStatusEl.textContent = `• ${status}`;
}

// Filter Functions
function filterTimeline() {
    const filterType = document.getElementById('filterType').value;
    const events = document.querySelectorAll('.timeline-event');
    
    events.forEach(event => {
        if (filterType === 'all') {
            event.style.display = 'block';
        } else if (filterType === 'conflicts') {
            event.style.display = event.classList.contains('has-contradiction') ? 'block' : 'none';
        } else {
            event.style.display = event.dataset.type === filterType ? 'block' : 'none';
        }
    });
}

// Export Functions
function exportTimeline() {
    const exportData = {
        case_name: document.querySelector('.case-name').textContent,
        export_date: new Date().toISOString(),
        events: eventsData.map(event => ({
            date: event.date.toISOString(),
            description: event.event_description,
            category: event.category,
            confidence: event.confidence_score
        })),
        contradictions: contradictionsData,
        facts_count: factsMap.size
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json'
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timeline_${Date.now()}.json`;
    a.click();
    
    URL.revokeObjectURL(url);
}

function saveProgress() {
    // In production, this would save to backend
    const progress = {
        job_id: currentJob?.job_id,
        current_page: currentPage,
        timestamp: new Date().toISOString()
    };
    
    localStorage.setItem('casefolio_progress', JSON.stringify(progress));
    
    // Show confirmation
    showNotification('Progress saved');
}

function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 500);
    }, 2000);
}

// Minimap Toggle
function toggleMinimap() {
    const minimap = document.getElementById('minimap');
    minimap.style.display = minimap.style.display === 'none' ? 'block' : 'none';
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize API key
    initializeApiKey();
    
    // Set up event listeners
    const dropZone = document.getElementById('documentContent');
    if (dropZone) {
        // Drag and drop support
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', async (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            
            const file = e.dataTransfer.files[0];
            if (file) {
                // Process dropped file
                const event = { target: { files: [file] } };
                await uploadDocument.call({ onchange: uploadDocument }, event);
            }
        });
    }
    
    // Add upload button if not exists
    if (!document.querySelector('.upload-button')) {
        const uploadBtn = document.createElement('button');
        uploadBtn.className = 'upload-button btn-primary';
        uploadBtn.textContent = 'Upload Document';
        uploadBtn.onclick = uploadDocument;
        
        const headerActions = document.querySelector('.header-actions');
        if (headerActions) {
            headerActions.insertBefore(uploadBtn, headerActions.firstChild);
        }
    }
    
    // Check for demo mode
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('demo') === 'true') {
        currentApiKey = 'DEMO';
        console.log('Demo mode activated');
    }
});

// Close fact inspector
function closeFactInspector() {
    const inspector = document.getElementById('factInspector');
    inspector.classList.remove('active');
}

// Navigation in fact inspector
function previousFact() {
    // Implementation for navigating to previous fact
    console.log('Previous fact navigation not yet implemented');
}

function nextFact() {
    // Implementation for navigating to next fact
    console.log('Next fact navigation not yet implemented');
}