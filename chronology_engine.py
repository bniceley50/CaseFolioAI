"""
CaseFolio AI Chronology Engine - Phase 1
A foundational module for parsing medical records and building case chronologies.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Document:
    """Represents a legal document with metadata and content."""
    name: str
    type: str  # e.g., 'medical_record', 'deposition', 'police_report'
    raw_text: str


@dataclass
class CaseEvent:
    """Represents a timestamped event extracted from a document."""
    date: datetime
    source_doc: str
    content: str
    tags: List[str] = field(default_factory=list)


def parse_medical_record(doc: Document) -> List[CaseEvent]:
    """
    Parse a medical record document to extract timestamped events.
    
    Searches for lines matching 'YYYY-MM-DD: ...' pattern and converts them
    to CaseEvent objects with auto-generated medical tags.
    
    Args:
        doc: Document object containing medical record text
        
    Returns:
        List of CaseEvent objects extracted from the document
    """
    events = []
    
    # Regex pattern to match lines starting with ISO date format
    date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}):\s*(.+)$', re.MULTILINE)
    
    # Medical keywords for auto-tagging
    medical_keywords = {
        'diagnosis', 'diagnosed', 'symptoms', 'medication', 'prescribed',
        'examination', 'test', 'results', 'treatment', 'procedure',
        'pain', 'injury', 'surgery', 'therapy', 'consultation'
    }
    
    for match in date_pattern.finditer(doc.raw_text):
        date_str, content = match.groups()
        
        try:
            # Parse the date
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Extract tags based on medical keywords found in content
            tags = []
            content_lower = content.lower()
            for keyword in medical_keywords:
                if keyword in content_lower:
                    tags.append(keyword)
            
            # If no specific tags found, add generic 'medical' tag
            if not tags:
                tags.append('medical')
            
            # Create and append the event
            event = CaseEvent(
                date=event_date,
                source_doc=doc.name,
                content=content.strip(),
                tags=tags
            )
            events.append(event)
            
        except ValueError:
            # Skip lines with invalid date formats
            continue
    
    return events


def build_master_chronology(events: List[CaseEvent]) -> List[CaseEvent]:
    """
    Build a master chronology by sorting events chronologically.
    
    Args:
        events: List of CaseEvent objects from various sources
        
    Returns:
        New list of CaseEvent objects sorted by date (earliest first)
    """
    # Sort events by date, maintaining stable sort for same-date events
    return sorted(events, key=lambda e: e.date)


if __name__ == "__main__":
    # Test harness demonstrating the complete workflow
    
    # Create a mock medical record document
    sample_medical_record = Document(
        name="patient_jane_doe_medical_2024.txt",
        type="medical_record",
        raw_text="""
PATIENT: Jane Doe
DOB: 1985-03-15
MRN: 12345

MEDICAL HISTORY TIMELINE:

2024-01-15: Initial consultation for lower back pain. Patient reports pain level 7/10.
2024-01-20: MRI examination ordered. Results show herniated disc at L4-L5.
2024-02-01: Started physical therapy treatment program, 3x per week.
2024-02-15: Follow-up examination. Pain reduced to 5/10. Prescribed muscle relaxants.
2024-03-01: Patient reports significant improvement. Pain level now 3/10.
Invalid date: This line should be skipped.
2024-03-15: Therapy sessions reduced to 1x per week. Excellent progress noted.
2024-04-01: Final assessment. Patient reports full recovery. Discharged from care.

Additional notes: Patient responded well to conservative treatment approach.
"""
    )
    
    # Step 1: Parse the medical record
    print("=== CASEFOLIO AI CHRONOLOGY ENGINE ===\n")
    print(f"Processing document: {sample_medical_record.name}")
    print(f"Document type: {sample_medical_record.type}\n")
    
    parsed_events = parse_medical_record(sample_medical_record)
    print(f"Successfully extracted {len(parsed_events)} events from medical record.\n")
    
    # Step 2: Build the master chronology
    chronology = build_master_chronology(parsed_events)
    
    # Step 3: Display the chronology in a clean format
    print("=== MASTER CASE CHRONOLOGY ===\n")
    for i, event in enumerate(chronology, 1):
        print(f"Event #{i}")
        print(f"  Date: {event.date.strftime('%Y-%m-%d')}")
        print(f"  Source: {event.source_doc}")
        print(f"  Content: {event.content}")
        print(f"  Tags: {', '.join(event.tags)}")
        print()
    
    print("=== CHRONOLOGY COMPLETE ===")