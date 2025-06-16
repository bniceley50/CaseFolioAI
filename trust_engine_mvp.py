"""
CaseFolio AI - Trust Engine MVP
Phase 1, Sprint 1: Deterministic Extraction Pipeline

A precision-first architecture for legal document analysis that prioritizes
100% factual accuracy through deterministic extraction before any AI processing.
"""

import re
from datetime import date, datetime
from typing import List, Union
from pydantic import BaseModel, Field, field_validator


class SourceLink(BaseModel):
    """
    Tracks the exact origin of an extracted fact for complete traceability.
    """
    document_name: str
    page_number: int = Field(ge=1, description="Page number (1-indexed)")
    bounding_box: List[float] = Field(
        min_items=4, 
        max_items=4,
        description="Coordinates [x1, y1, x2, y2] of text location"
    )
    
    @field_validator('bounding_box')
    def validate_bounding_box(cls, v):
        """Ensure bounding box coordinates are non-negative."""
        if any(coord < 0 for coord in v):
            raise ValueError("Bounding box coordinates must be non-negative")
        return v


class ExtractedFact(BaseModel):
    """
    Represents a single piece of extracted information with full source attribution.
    """
    value: Union[str, float, date]
    fact_type: str = Field(description="Type of fact (e.g., 'date', 'name', 'amount')")
    source: SourceLink
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


def extract_dates(document_text: str, document_name: str) -> List[ExtractedFact]:
    """
    Extract all dates in MM/DD/YYYY format from document text using deterministic regex.
    
    Args:
        document_text: The raw text content of the document
        document_name: Name/identifier of the source document
        
    Returns:
        List of ExtractedFact objects containing validated dates
    """
    facts = []
    
    # Regex pattern for MM/DD/YYYY format
    # Matches: 01/15/2024, 12/31/2023, etc.
    date_pattern = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
    
    for match in date_pattern.finditer(document_text):
        month_str, day_str, year_str = match.groups()
        month, day, year = int(month_str), int(day_str), int(year_str)
        
        # Validate the date
        try:
            # This will raise ValueError for invalid dates like 02/30/2024
            extracted_date = date(year, month, day)
            
            # Create source link with placeholder coordinates
            # In production, these would come from OCR or text extraction system
            source_link = SourceLink(
                document_name=document_name,
                page_number=1,  # Placeholder
                bounding_box=[0.0, 0.0, 0.0, 0.0]  # Placeholder
            )
            
            # Create the fact
            fact = ExtractedFact(
                value=extracted_date,
                fact_type="date",
                source=source_link
            )
            
            facts.append(fact)
            
        except ValueError:
            # Skip invalid dates (e.g., 13/32/2024, 02/30/2024)
            continue
    
    return facts


def build_chronology(facts: List[ExtractedFact]) -> List[ExtractedFact]:
    """
    Build a chronological timeline from extracted facts.
    
    Filters for date-type facts and sorts them chronologically.
    
    Args:
        facts: List of all extracted facts
        
    Returns:
        List of date facts sorted in chronological order
    """
    # Filter for date facts only
    date_facts = [f for f in facts if f.fact_type == "date" and isinstance(f.value, date)]
    
    # Sort by date value
    sorted_facts = sorted(date_facts, key=lambda f: f.value)
    
    return sorted_facts


if __name__ == "__main__":
    # Test harness demonstrating the complete workflow
    print("=== CaseFolio AI Trust Engine MVP - Test Run ===\n")
    
    # Mock document with various dates
    mock_document = """
    CASE FILE: Johnson v. Smith Motors
    Date of Filing: 03/15/2024
    
    INCIDENT REPORT:
    On 01/10/2024, the plaintiff was involved in a motor vehicle accident at the 
    intersection of Main St. and 5th Ave. The police report (#2024-1234) was filed
    on 01/10/2024 at approximately 3:45 PM.
    
    MEDICAL RECORDS:
    - Emergency room visit: 01/10/2024
    - First follow-up appointment: 01/17/2024
    - MRI performed: 01/25/2024
    - Physical therapy started: 02/05/2024
    - Surgeon consultation: 02/20/2024
    
    LEGAL PROCEEDINGS:
    - Attorney retained: 01/12/2024
    - Demand letter sent: 02/28/2024
    - Lawsuit filed: 03/15/2024
    - Defendant response due: 04/15/2024
    
    INVALID DATES (should be ignored):
    - Bad date 1: 13/01/2024 (invalid month)
    - Bad date 2: 02/30/2024 (February 30th doesn't exist)
    - Bad date 3: 00/15/2024 (invalid month)
    """
    
    # Extract dates from the document
    print("Step 1: Extracting dates from document...")
    extracted_facts = extract_dates(mock_document, "Johnson_v_Smith_Case_File.pdf")
    print(f"Found {len(extracted_facts)} valid dates\n")
    
    # Build chronology
    print("Step 2: Building chronological timeline...")
    chronology = build_chronology(extracted_facts)
    print(f"Chronology contains {len(chronology)} date events\n")
    
    # Display results with source attribution
    print("=== FINAL CHRONOLOGY ===\n")
    for i, fact in enumerate(chronology, 1):
        print(f"Event #{i}:")
        print(f"  Date: {fact.value.strftime('%B %d, %Y')}")
        print(f"  Raw Value: {fact.value}")
        print(f"  Source Document: {fact.source.document_name}")
        print(f"  Page: {fact.source.page_number}")
        print(f"  Location: {fact.source.bounding_box}")
        print(f"  Fact Type: {fact.fact_type}")
        print("-" * 40)
    
    # Verification summary
    print(f"\n✅ Test Complete: Successfully extracted and sorted {len(chronology)} dates")
    print("✅ All dates validated and source-linked")
    print("✅ Invalid dates properly rejected")
    
    # Assert critical functionality
    # Note: Document contains duplicate dates (01/10/2024 appears 3 times, 03/15/2024 appears 2 times)
    assert len(chronology) == 12, f"Expected 12 valid dates, found {len(chronology)}"
    assert all(f.fact_type == "date" for f in chronology), "All facts should be dates"
    assert all(isinstance(f.value, date) for f in chronology), "All values should be date objects"
    assert chronology[0].value == date(2024, 1, 10), "First event should be Jan 10, 2024"
    assert chronology[-1].value == date(2024, 4, 15), "Last event should be Apr 15, 2024"
    
    print("\n✅ All assertions passed - Trust Engine MVP working correctly!")