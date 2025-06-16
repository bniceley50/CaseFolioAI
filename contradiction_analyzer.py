"""
CaseFolio AI - Contradiction Analyzer
Hybrid approach using deterministic rules + GPT-4 for high-value contradiction detection
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import date, datetime
from openai import OpenAI
from dotenv import load_dotenv

from intelligence_engine_phase2 import SynthesizedEvent

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class ContradictionAnalyzer:
    """
    Analyzes events for logical contradictions using a hybrid approach:
    1. Rule-based candidate detection
    2. GPT-4 confirmation and explanation
    """
    
    def __init__(self):
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found, using mock mode")
            self.mock_mode = True
            self.client = None
        else:
            self.mock_mode = False
            self.client = OpenAI(api_key=api_key)
        
        # Model configuration for high-value analysis
        self.model = "gpt-4"  # Use GPT-4 for accuracy
        self.max_tokens = 200
        self.temperature = 0.1  # Very low temperature for consistency
        
        # Contradiction patterns (deterministic rules)
        self.contradiction_patterns = [
            {
                'pattern': 'injury_denial_after_report',
                'keywords_1': ['injury', 'pain', 'accident', 'trauma', 'hurt'],
                'keywords_2': ['no pain', 'felt fine', 'no injury', 'denied', 'no issues'],
                'description': 'Denial of injury after documented medical treatment'
            },
            {
                'pattern': 'timeline_conflict',
                'keywords_1': ['before', 'prior to', 'earlier'],
                'keywords_2': ['after', 'following', 'later'],
                'description': 'Conflicting timeline of events'
            },
            {
                'pattern': 'treatment_inconsistency',
                'keywords_1': ['treatment', 'therapy', 'medication'],
                'keywords_2': ['no treatment', 'refused care', 'declined'],
                'description': 'Inconsistent treatment claims'
            }
        ]
    
    def analyze_contradictions(self, events: List[SynthesizedEvent]) -> List[Dict[str, Any]]:
        """
        Analyze events for contradictions
        
        Args:
            events: List of synthesized events to analyze
            
        Returns:
            List of detected contradictions with explanations
        """
        contradictions = []
        
        # Step 1: Find candidate pairs using rules
        candidate_pairs = self._find_candidate_pairs(events)
        
        # Step 2: Analyze each candidate with GPT-4
        for event1, event2, pattern in candidate_pairs:
            contradiction = self._analyze_pair_with_llm(event1, event2, pattern)
            if contradiction:
                contradictions.append(contradiction)
        
        return contradictions
    
    def _find_candidate_pairs(self, events: List[SynthesizedEvent]) -> List[Tuple[SynthesizedEvent, SynthesizedEvent, Dict]]:
        """Find potential contradiction pairs using rule-based patterns"""
        candidates = []
        
        # Compare each event pair
        for i, event1 in enumerate(events):
            for j, event2 in enumerate(events[i+1:], i+1):
                # Check each pattern
                for pattern in self.contradiction_patterns:
                    if self._matches_pattern(event1, event2, pattern):
                        candidates.append((event1, event2, pattern))
        
        return candidates
    
    def _matches_pattern(self, event1: SynthesizedEvent, event2: SynthesizedEvent, pattern: Dict) -> bool:
        """Check if two events match a contradiction pattern"""
        desc1 = event1.event_description.lower()
        desc2 = event2.event_description.lower()
        
        # Check if keywords from pattern appear in opposite events
        has_keywords_1_in_1 = any(kw in desc1 for kw in pattern['keywords_1'])
        has_keywords_2_in_2 = any(kw in desc2 for kw in pattern['keywords_2'])
        
        has_keywords_1_in_2 = any(kw in desc2 for kw in pattern['keywords_1'])
        has_keywords_2_in_1 = any(kw in desc1 for kw in pattern['keywords_2'])
        
        # Pattern matches if keywords appear in conflicting ways
        return (has_keywords_1_in_1 and has_keywords_2_in_2) or \
               (has_keywords_1_in_2 and has_keywords_2_in_1)
    
    def _analyze_pair_with_llm(self, event1: SynthesizedEvent, event2: SynthesizedEvent, 
                              pattern: Dict) -> Optional[Dict[str, Any]]:
        """Use GPT-4 to confirm and explain contradiction"""
        if self.mock_mode:
            return self._mock_analyze_contradiction(event1, event2, pattern)
        
        # Build prompt for GPT-4
        prompt = self._build_analysis_prompt(event1, event2, pattern)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a legal analyst examining potential contradictions in case documentation. "
                                  "Analyze the provided events and determine if they truly contradict each other. "
                                  "Respond with a JSON object containing your analysis."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Parse response
            analysis = json.loads(response.choices[0].message.content)
            
            # If confirmed as contradiction, format result
            if analysis.get('is_contradiction', False):
                return {
                    'id': f"contradiction_{event1.event_date}_{event2.event_date}",
                    'type': pattern['pattern'],
                    'severity': analysis.get('severity', 'medium'),
                    'confidence': analysis.get('confidence', 0.85),
                    'event_1': {
                        'date': event1.event_date.isoformat(),
                        'description': event1.event_description
                    },
                    'event_2': {
                        'date': event2.event_date.isoformat(),
                        'description': event2.event_description
                    },
                    'explanation': analysis.get('explanation', 'Conflicting information detected'),
                    'impact': analysis.get('impact', 'May affect case credibility')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing contradiction with GPT-4: {str(e)}")
            return None
    
    def _build_analysis_prompt(self, event1: SynthesizedEvent, event2: SynthesizedEvent, 
                               pattern: Dict) -> str:
        """Build structured prompt for GPT-4 analysis"""
        prompt = f"""Analyze these two events for potential contradiction:

Event 1 (Date: {event1.event_date}):
"{event1.event_description}"

Event 2 (Date: {event2.event_date}):
"{event2.event_description}"

Potential Issue: {pattern['description']}

Please analyze whether these events truly contradict each other. Consider:
1. Are the statements mutually exclusive?
2. Could both statements be true under different interpretations?
3. What is the severity of the contradiction if it exists?

Respond with a JSON object containing:
{{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "severity": "low"|"medium"|"high",
    "explanation": "Clear explanation of the contradiction",
    "impact": "How this affects the case"
}}
"""
        return prompt
    
    def _mock_analyze_contradiction(self, event1: SynthesizedEvent, event2: SynthesizedEvent, 
                                   pattern: Dict) -> Optional[Dict[str, Any]]:
        """Mock contradiction analysis for testing"""
        # Simulate some known contradictions
        if pattern['pattern'] == 'injury_denial_after_report':
            if 'injury' in event1.event_description.lower() and \
               'no pain' in event2.event_description.lower():
                return {
                    'id': f"contradiction_mock_1",
                    'type': 'injury_denial_after_report',
                    'severity': 'high',
                    'confidence': 0.92,
                    'event_1': {
                        'date': event1.event_date.isoformat(),
                        'description': event1.event_description
                    },
                    'event_2': {
                        'date': event2.event_date.isoformat(),
                        'description': event2.event_description
                    },
                    'explanation': "Patient denied experiencing pain during deposition despite documented emergency room treatment for injuries.",
                    'impact': "This contradiction could significantly impact the credibility of injury claims."
                }
        
        return None


class ContradictionReport:
    """Generate formatted contradiction reports"""
    
    @staticmethod
    def generate_summary(contradictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of all contradictions"""
        if not contradictions:
            return {
                'total_contradictions': 0,
                'severity_breakdown': {},
                'risk_assessment': 'No contradictions detected'
            }
        
        # Count by severity
        severity_counts = {'low': 0, 'medium': 0, 'high': 0}
        for c in contradictions:
            severity = c.get('severity', 'medium')
            severity_counts[severity] += 1
        
        # Risk assessment
        risk_level = 'low'
        if severity_counts['high'] > 0:
            risk_level = 'high'
        elif severity_counts['medium'] > 1:
            risk_level = 'medium'
        
        return {
            'total_contradictions': len(contradictions),
            'severity_breakdown': severity_counts,
            'risk_assessment': f"Case has {risk_level} risk due to contradictions",
            'high_priority_count': severity_counts['high']
        }