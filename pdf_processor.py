"""
CaseFolio AI - Production PDF Processor
High-precision PDF text extraction with coordinate-level data using PyMuPDF
"""

import fitz  # PyMuPDF
import re
from typing import List, Dict, Tuple, Optional, Any
from datetime import date
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Production-grade PDF processor that extracts text with precise coordinate data
    for the ChronoAnchor™ Click-to-Anchor functionality.
    """
    
    def __init__(self):
        self.date_pattern = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
        self.money_pattern = re.compile(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
        self.name_pattern = re.compile(r'\b(Dr\.|Mr\.|Mrs\.|Ms\.)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:,\s*(?:MD|JD|PhD|RN|Esq\.))?')
        
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a PDF file and extract text with full positional data.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing:
                - pages: List of page data with text and positions
                - metadata: Document metadata
                - total_pages: Total number of pages
        """
        try:
            doc = fitz.open(pdf_path)
            
            result = {
                'pages': [],
                'metadata': doc.metadata,
                'total_pages': len(doc),
                'filename': Path(pdf_path).name
            }
            
            for page_num, page in enumerate(doc):
                page_data = self.extract_page_with_positions(page, page_num + 1)
                result['pages'].append(page_data)
            
            doc.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
    
    def extract_page_with_positions(self, page: fitz.Page, page_number: int) -> Dict[str, Any]:
        """
        Extract text from a page with word-level position data.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-indexed page number
            
        Returns:
            Dictionary containing:
                - page_number: Page number
                - text: Full page text
                - words: List of words with bounding boxes
                - dimensions: Page dimensions
        """
        # Get page dimensions
        rect = page.rect
        dimensions = {
            'width': rect.width,
            'height': rect.height
        }
        
        # Extract text as dictionary with full structure
        text_dict = page.get_text("dict")
        
        # Extract plain text for compatibility
        plain_text = page.get_text()
        
        # Extract words with positions
        words = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            words.append({
                                'text': text,
                                'bbox': bbox,  # [x0, y0, x1, y1]
                                'line_num': line.get("line_no", 0),
                                'block_num': block.get("number", 0)
                            })
        
        return {
            'page_number': page_number,
            'text': plain_text,
            'words': words,
            'dimensions': dimensions,
            'blocks': text_dict.get("blocks", [])
        }
    
    def extract_facts_with_positions(self, page_data: Dict[str, Any], document_name: str) -> List[Dict[str, Any]]:
        """
        Extract facts from page data with precise bounding box coordinates.
        
        Args:
            page_data: Page data from extract_page_with_positions
            document_name: Name of the document
            
        Returns:
            List of extracted facts with coordinate data
        """
        facts = []
        page_number = page_data['page_number']
        
        # Process text spans to find facts
        for block in page_data.get('blocks', []):
            if block.get('type') == 0:  # Text block
                block_text = ""
                span_positions = []
                
                # Build block text and track positions
                for line in block.get('lines', []):
                    line_start = len(block_text)
                    for span in line.get('spans', []):
                        span_text = span.get('text', '')
                        span_start = len(block_text)
                        block_text += span_text
                        span_positions.append({
                            'start': span_start,
                            'end': span_start + len(span_text),
                            'bbox': span.get('bbox', [0, 0, 0, 0]),
                            'text': span_text
                        })
                    block_text += " "  # Add space between lines
                
                # Extract dates with positions
                facts.extend(self._extract_dates_from_block(
                    block_text, span_positions, page_number, document_name
                ))
                
                # Extract monetary amounts with positions
                facts.extend(self._extract_amounts_from_block(
                    block_text, span_positions, page_number, document_name
                ))
                
                # Extract names with positions
                facts.extend(self._extract_names_from_block(
                    block_text, span_positions, page_number, document_name
                ))
        
        return facts
    
    def _extract_dates_from_block(self, text: str, span_positions: List[Dict], 
                                  page_number: int, document_name: str) -> List[Dict[str, Any]]:
        """Extract dates with precise bounding boxes."""
        facts = []
        
        for match in self.date_pattern.finditer(text):
            month_str, day_str, year_str = match.groups()
            
            try:
                month, day, year = int(month_str), int(day_str), int(year_str)
                extracted_date = date(year, month, day)
                
                # Find bounding box for the matched text
                match_start = match.start()
                match_end = match.end()
                bbox = self._get_match_bbox(match_start, match_end, span_positions)
                
                if bbox:
                    facts.append({
                        'value': extracted_date,
                        'fact_type': 'date',
                        'page_number': page_number,
                        'bounding_box': bbox,
                        'document_name': document_name,
                        'text_match': match.group(0)
                    })
                    
            except ValueError:
                continue
        
        return facts
    
    def _extract_amounts_from_block(self, text: str, span_positions: List[Dict],
                                   page_number: int, document_name: str) -> List[Dict[str, Any]]:
        """Extract monetary amounts with precise bounding boxes."""
        facts = []
        
        for match in self.money_pattern.finditer(text):
            money_str = match.group(1)
            money_value = float(money_str.replace(',', ''))
            
            # Find bounding box
            match_start = match.start()
            match_end = match.end()
            bbox = self._get_match_bbox(match_start, match_end, span_positions)
            
            if bbox:
                facts.append({
                    'value': money_value,
                    'fact_type': 'amount',
                    'page_number': page_number,
                    'bounding_box': bbox,
                    'document_name': document_name,
                    'text_match': match.group(0)
                })
        
        return facts
    
    def _extract_names_from_block(self, text: str, span_positions: List[Dict],
                                 page_number: int, document_name: str) -> List[Dict[str, Any]]:
        """Extract person names with precise bounding boxes."""
        facts = []
        
        for match in self.name_pattern.finditer(text):
            full_match = match.group(0).strip()
            
            # Find bounding box
            match_start = match.start()
            match_end = match.end()
            bbox = self._get_match_bbox(match_start, match_end, span_positions)
            
            if bbox:
                facts.append({
                    'value': full_match,
                    'fact_type': 'person_name',
                    'page_number': page_number,
                    'bounding_box': bbox,
                    'document_name': document_name,
                    'text_match': full_match
                })
        
        return facts
    
    def _get_match_bbox(self, start: int, end: int, span_positions: List[Dict]) -> Optional[List[float]]:
        """
        Calculate bounding box for a text match by combining span bounding boxes.
        
        Args:
            start: Start position of match in text
            end: End position of match in text
            span_positions: List of span position data
            
        Returns:
            Combined bounding box [x0, y0, x1, y1] or None
        """
        matching_spans = []
        
        for span in span_positions:
            # Check if this span overlaps with our match
            if span['end'] > start and span['start'] < end:
                matching_spans.append(span)
        
        if not matching_spans:
            return None
        
        # Combine bounding boxes
        x0 = min(span['bbox'][0] for span in matching_spans)
        y0 = min(span['bbox'][1] for span in matching_spans)
        x1 = max(span['bbox'][2] for span in matching_spans)
        y1 = max(span['bbox'][3] for span in matching_spans)
        
        return [x0, y0, x1, y1]
    
    def process_text_with_mock_positions(self, text: str, document_name: str) -> Dict[str, Any]:
        """
        Process plain text with simulated position data for testing.
        Used when PDF processing is not available.
        
        Args:
            text: Plain text content
            document_name: Document name
            
        Returns:
            Document data with mock positions
        """
        lines = text.split('\n')
        page_height = 792  # Standard letter size
        line_height = 12
        margin = 72
        
        pages = []
        current_page_lines = []
        current_y = margin
        page_num = 1
        
        for line in lines:
            if current_y + line_height > page_height - margin:
                # Start new page
                pages.append({
                    'page_number': page_num,
                    'text': '\n'.join(current_page_lines),
                    'words': self._create_mock_words(current_page_lines, page_num),
                    'dimensions': {'width': 612, 'height': page_height}
                })
                page_num += 1
                current_page_lines = []
                current_y = margin
            
            current_page_lines.append(line)
            current_y += line_height
        
        # Add last page
        if current_page_lines:
            pages.append({
                'page_number': page_num,
                'text': '\n'.join(current_page_lines),
                'words': self._create_mock_words(current_page_lines, page_num),
                'dimensions': {'width': 612, 'height': page_height}
            })
        
        return {
            'pages': pages,
            'metadata': {},
            'total_pages': len(pages),
            'filename': document_name
        }
    
    def _create_mock_words(self, lines: List[str], page_num: int) -> List[Dict]:
        """Create mock word position data for testing."""
        words = []
        y = 72  # Start at top margin
        
        for line in lines:
            x = 72  # Left margin
            for word in line.split():
                # Estimate width based on character count
                width = len(word) * 7
                words.append({
                    'text': word,
                    'bbox': [x, y, x + width, y + 12],
                    'line_num': len(words),
                    'block_num': 1
                })
                x += width + 5  # Space between words
            y += 14  # Line spacing
        
        return words