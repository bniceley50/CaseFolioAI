"""
CaseFolio AI - Trust Engine MVP
Phase 1, Sprint 2: Expanded Extraction Pipeline

Building on Sprint 1, this extends the precision-first architecture to handle
multiple fact types (dates, monetary amounts, person names) with document segmentation.
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


def extract_facts_from_prose(document_text: str, document_name: str) -> List[ExtractedFact]:
    """
    Extract facts from prose sections of documents using deterministic regex.
    Currently extracts dates in MM/DD/YYYY format.
    
    Args:
        document_text: The raw text content of the prose section
        document_name: Name/identifier of the source document
        
    Returns:
        List of ExtractedFact objects containing validated facts
    """
    facts = []
    
    # Regex pattern for MM/DD/YYYY format dates
    date_pattern = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
    
    for match in date_pattern.finditer(document_text):
        month_str, day_str, year_str = match.groups()
        month, day, year = int(month_str), int(day_str), int(year_str)
        
        # Validate the date
        try:
            extracted_date = date(year, month, day)
            
            # Create source link with placeholder coordinates
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
            # Skip invalid dates
            continue
    
    return facts


def extract_facts_from_table(table_text: str, document_name: str) -> List[ExtractedFact]:
    """
    Extract structured facts from table sections of documents.
    Extracts monetary values and person names following specific patterns.
    
    Args:
        table_text: The raw text content of the table section
        document_name: Name/identifier of the source document
        
    Returns:
        List of ExtractedFact objects containing monetary amounts and names
    """
    facts = []
    
    # Also extract dates from table section
    date_pattern = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
    
    for match in date_pattern.finditer(table_text):
        month_str, day_str, year_str = match.groups()
        month, day, year = int(month_str), int(day_str), int(year_str)
        
        try:
            extracted_date = date(year, month, day)
            
            source_link = SourceLink(
                document_name=document_name,
                page_number=2,  # Tables on page 2
                bounding_box=[0.0, 0.0, 0.0, 0.0]
            )
            
            fact = ExtractedFact(
                value=extracted_date,
                fact_type="date",
                source=source_link
            )
            
            facts.append(fact)
            
        except ValueError:
            continue
    
    # Regex pattern for monetary values like $1,234.56 or $1234.56
    money_pattern = re.compile(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
    
    for match in money_pattern.finditer(table_text):
        money_str = match.group(1)
        # Remove commas and convert to float
        money_value = float(money_str.replace(',', ''))
        
        # Create source link
        source_link = SourceLink(
            document_name=document_name,
            page_number=2,  # Placeholder - assuming tables on page 2
            bounding_box=[0.0, 0.0, 0.0, 0.0]  # Placeholder
        )
        
        # Create the fact
        fact = ExtractedFact(
            value=money_value,
            fact_type="amount",
            source=source_link
        )
        
        facts.append(fact)
    
    # Regex pattern for names following "Provider:" label
    # Captures names that may include titles, credentials, and parenthetical notes
    provider_pattern = re.compile(r'Provider:\s*([A-Za-z\s\.,\-]+(?:\([^)]+\))?)\s*(?=\n|$)')
    
    for match in provider_pattern.finditer(table_text):
        name = match.group(1).strip()
        
        # Clean up the name (remove trailing punctuation unless it's part of credentials)
        if not name.endswith(')'):
            name = name.rstrip('., ')
        
        # Create source link
        source_link = SourceLink(
            document_name=document_name,
            page_number=2,  # Placeholder
            bounding_box=[0.0, 0.0, 0.0, 0.0]  # Placeholder
        )
        
        # Create the fact
        fact = ExtractedFact(
            value=name,
            fact_type="person_name",
            source=source_link
        )
        
        facts.append(fact)
    
    return facts


def process_document(doc_text: str, document_name: str) -> List[ExtractedFact]:
    """
    Main orchestrator that segments documents and routes to appropriate extractors.
    
    Splits document at ---TABLE--- marker and processes each section with
    the appropriate specialized extractor.
    
    Args:
        doc_text: The complete document text
        document_name: Name/identifier of the source document
        
    Returns:
        Combined list of all extracted facts from all sections
    """
    all_facts = []
    
    # Split document into prose and table sections
    if '---TABLE---' in doc_text:
        parts = doc_text.split('---TABLE---', 1)
        prose_section = parts[0]
        table_section = parts[1] if len(parts) > 1 else ""
    else:
        # If no table marker, treat entire document as prose
        prose_section = doc_text
        table_section = ""
    
    # Extract facts from prose section
    prose_facts = extract_facts_from_prose(prose_section, document_name)
    all_facts.extend(prose_facts)
    
    # Extract facts from table section if present
    if table_section:
        table_facts = extract_facts_from_table(table_section, document_name)
        all_facts.extend(table_facts)
    
    return all_facts


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
    # Test harness demonstrating Sprint 2 capabilities
    print("=== CaseFolio AI Trust Engine MVP - Sprint 2 Test ===\n")
    
    # Mock document with both prose and table sections
    mock_document = """
    CASE FILE: Johnson v. Smith Motors
    Date of Filing: 03/15/2024
    
    INCIDENT REPORT:
    On 01/10/2024, the plaintiff was involved in a motor vehicle accident at the 
    intersection of Main St. and 5th Ave. The initial medical evaluation was
    performed on 01/10/2024 at Mercy Hospital Emergency Room.
    
    FOLLOW-UP CARE:
    The patient returned for evaluation on 01/17/2024 and began a course of
    treatment that continued through 02/28/2024.
    
    ---TABLE---
    
    MEDICAL EXPENSES SUMMARY
    
    Service: Emergency Room Visit
    Provider: Dr. Sarah Johnson, MD
    Date: 01/10/2024
    Amount: $3,450.00
    
    Service: MRI Imaging
    Provider: Mercy Hospital Radiology
    Date: 01/25/2024
    Amount: $2,800.00
    
    Service: Physical Therapy (8 sessions)
    Provider: Dr. Michael Chen, PT, DPT
    Date Range: 02/05/2024 - 02/28/2024
    Amount: $1,200.00
    
    Service: Orthopedic Consultation
    Provider: Dr. Robert Smith, MD, FAAOS
    Date: 02/20/2024
    Amount: $750.00
    
    TOTAL MEDICAL EXPENSES: $8,200.00
    
    Additional Notes:
    - All providers are board certified
    - Insurance coverage pending
    - Provider: Dr. Jane Doe (primary care physician - not treating)
    """
    
    # Process the document
    print("Step 1: Processing document with orchestrator...")
    all_facts = process_document(mock_document, "Johnson_v_Smith_Medical_Summary.pdf")
    print(f"Total facts extracted: {len(all_facts)}")
    
    # Count by type
    date_count = sum(1 for f in all_facts if f.fact_type == "date")
    amount_count = sum(1 for f in all_facts if f.fact_type == "amount")
    name_count = sum(1 for f in all_facts if f.fact_type == "person_name")
    
    print(f"  - Dates: {date_count}")
    print(f"  - Amounts: {amount_count}")
    print(f"  - Names: {name_count}\n")
    
    # Display all extracted facts
    print("=== ALL EXTRACTED FACTS ===\n")
    for i, fact in enumerate(all_facts, 1):
        print(f"Fact #{i}:")
        print(f"  Type: {fact.fact_type}")
        if fact.fact_type == "date":
            print(f"  Value: {fact.value.strftime('%B %d, %Y')}")
        elif fact.fact_type == "amount":
            print(f"  Value: ${fact.value:,.2f}")
        else:
            print(f"  Value: {fact.value}")
        print(f"  Source: {fact.source.document_name} (page {fact.source.page_number})")
        print("-" * 40)
    
    # Build chronology (dates only)
    print("\n=== CHRONOLOGICAL TIMELINE (DATES ONLY) ===\n")
    chronology = build_chronology(all_facts)
    
    for i, fact in enumerate(chronology, 1):
        print(f"Event #{i}: {fact.value.strftime('%B %d, %Y')}")
    
    # Verification assertions
    print("\n=== VERIFICATION ===")
    
    # Assert correct number of each fact type
    assert date_count == 10, f"Expected 10 dates, found {date_count}"
    assert amount_count == 5, f"Expected 5 amounts, found {amount_count}"
    assert name_count == 5, f"Expected 5 names, found {name_count}"
    
    # Verify specific values
    amounts = [f.value for f in all_facts if f.fact_type == "amount"]
    assert 3450.0 in amounts, "Emergency room cost not found"
    assert 8200.0 in amounts, "Total amount not found"
    
    names = [f.value for f in all_facts if f.fact_type == "person_name"]
    assert "Dr. Sarah Johnson, MD" in names, "Dr. Johnson not found"
    assert "Dr. Michael Chen, PT, DPT" in names, "Dr. Chen not found"
    
    # Verify chronology
    assert len(chronology) == 10, f"Expected 10 dates in chronology, found {len(chronology)}"
    assert chronology[0].value == date(2024, 1, 10), "First date should be Jan 10, 2024"
    assert chronology[-1].value == date(2024, 3, 15), "Last date should be Mar 15, 2024"
    
    print("\n✅ All assertions passed!")
    print("✅ Sprint 2 implementation working correctly!")
    print("✅ Successfully expanded to handle dates, amounts, and names!")