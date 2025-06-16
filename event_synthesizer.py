"""
CaseFolio AI - Event Synthesizer
Real LLM integration for contextual event synthesis using gpt-3.5-turbo
"""

import os
import json
import logging
from typing import List, Dict, Any
from datetime import date, datetime
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv

from intelligence_engine_phase2 import ExtractedFact, SynthesizedEvent

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class EventSynthesizer:
    """
    Synthesizes human-readable events from extracted facts using OpenAI's gpt-3.5-turbo
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
        
        # Model configuration
        self.model = "gpt-3.5-turbo"
        self.max_tokens = 100
        self.temperature = 0.3  # Lower temperature for consistency
        
        # Cost tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0
    
    def synthesize_events(self, facts: List[ExtractedFact]) -> List[SynthesizedEvent]:
        """
        Transform extracted facts into synthesized events using LLM
        
        Args:
            facts: List of extracted facts from documents
            
        Returns:
            List of synthesized events with AI-generated descriptions
        """
        # Group facts by date
        facts_by_date = self._group_facts_by_date(facts)
        
        # Generate synthesized events
        synthesized_events = []
        
        for event_date, date_facts in sorted(facts_by_date.items()):
            # Skip dates with only date facts (no meaningful content)
            non_date_facts = [f for f in date_facts if f.fact_type != "date"]
            if not non_date_facts and len(date_facts) <= 1:
                continue
            
            # Generate event description
            description = self._generate_event_description(event_date, date_facts)
            
            # Create synthesized event
            event = SynthesizedEvent(
                event_date=event_date,
                event_description=description,
                source_facts=date_facts
            )
            
            synthesized_events.append(event)
        
        # Log cost metrics
        if not self.mock_mode:
            logger.info(f"Synthesis complete. Total tokens: {self.total_tokens_used}, "
                       f"Estimated cost: ${self.total_cost:.4f}")
        
        return synthesized_events
    
    def _group_facts_by_date(self, facts: List[ExtractedFact]) -> Dict[date, List[ExtractedFact]]:
        """Group facts by their associated date"""
        facts_by_date = defaultdict(list)
        
        # First pass: collect all date facts
        for fact in facts:
            if fact.fact_type == "date" and isinstance(fact.value, date):
                facts_by_date[fact.value].append(fact)
        
        # Second pass: associate non-date facts with dates
        # This is a simplified heuristic - in production, use more sophisticated logic
        for fact in facts:
            if fact.fact_type != "date":
                # Associate with the closest date based on document structure
                # For MVP, we'll use page-based association
                best_date = self._find_closest_date(fact, facts)
                if best_date:
                    facts_by_date[best_date].append(fact)
        
        return facts_by_date
    
    def _find_closest_date(self, target_fact: ExtractedFact, all_facts: List[ExtractedFact]) -> date:
        """Find the most relevant date for a non-date fact"""
        # Find all date facts on the same page
        same_page_dates = [
            f for f in all_facts 
            if f.fact_type == "date" 
            and f.source.page_number == target_fact.source.page_number
            and isinstance(f.value, date)
        ]
        
        if same_page_dates:
            # Return the first date on the same page (simplified logic)
            return same_page_dates[0].value
        
        # If no dates on same page, return None
        return None
    
    def _generate_event_description(self, event_date: date, facts: List[ExtractedFact]) -> str:
        """Generate human-readable description using LLM"""
        if self.mock_mode:
            return self._mock_generate_description(event_date, facts)
        
        # Prepare fact summary for LLM
        fact_summary = self._prepare_fact_summary(facts)
        
        # Construct prompt
        prompt = self._build_synthesis_prompt(event_date, fact_summary)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a legal document analyst. Create concise, single-sentence summaries of events based on provided facts. Focus on clarity and accuracy."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Extract description
            description = response.choices[0].message.content.strip()
            
            # Track usage
            if response.usage:
                self.total_tokens_used += response.usage.total_tokens
                # Approximate cost for gpt-3.5-turbo (as of 2024)
                self.total_cost += (response.usage.prompt_tokens * 0.0005 + 
                                   response.usage.completion_tokens * 0.0015) / 1000
            
            return description
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            # Fallback to basic description
            return self._fallback_description(facts)
    
    def _prepare_fact_summary(self, facts: List[ExtractedFact]) -> List[Dict[str, Any]]:
        """Prepare facts in a structured format for the LLM"""
        summary = []
        
        for fact in facts:
            if fact.fact_type == "date":
                continue  # Skip date facts in summary
            
            fact_info = {
                "type": fact.fact_type.replace("_", " "),
                "value": str(fact.value)
            }
            
            # Add context based on fact type
            if fact.fact_type == "person_name":
                # Try to determine role
                if "MD" in str(fact.value) or "Dr." in str(fact.value):
                    fact_info["role"] = "medical provider"
                elif "PT" in str(fact.value):
                    fact_info["role"] = "physical therapist"
                elif "Hospital" in str(fact.value):
                    fact_info["role"] = "medical facility"
            
            summary.append(fact_info)
        
        return summary
    
    def _build_synthesis_prompt(self, event_date: date, fact_summary: List[Dict[str, Any]]) -> str:
        """Build the prompt for the LLM"""
        date_str = event_date.strftime("%B %d, %Y")
        
        prompt = f"Create a single, concise sentence describing what happened on {date_str} based on these facts:\n\n"
        
        for fact in fact_summary:
            prompt += f"- {fact['type']}: {fact['value']}"
            if 'role' in fact:
                prompt += f" ({fact['role']})"
            prompt += "\n"
        
        prompt += "\nGenerate a clear, professional summary sentence that captures the key information."
        
        return prompt
    
    def _mock_generate_description(self, event_date: date, facts: List[ExtractedFact]) -> str:
        """Mock description generator for testing without API key"""
        # Extract relevant information
        amounts = [f for f in facts if f.fact_type == "amount"]
        names = [f for f in facts if f.fact_type == "person_name"]
        
        if amounts and names:
            amount = amounts[0].value
            name = names[0].value
            
            # Generate contextual description based on patterns
            if "Emergency" in str(name) or "ER" in str(name):
                return f"Emergency medical treatment provided by {name} with charges of ${amount:,.2f}."
            elif "Radiology" in str(name):
                return f"Medical imaging services performed at {name} for ${amount:,.2f}."
            elif "PT" in str(name) or "Physical" in str(name):
                return f"Physical therapy treatment by {name} totaling ${amount:,.2f}."
            else:
                return f"Medical services provided by {name} with charges of ${amount:,.2f}."
        
        # Default descriptions
        if event_date.day == 10 and event_date.month == 1:
            return "Motor vehicle accident occurred with immediate medical evaluation."
        elif event_date.day == 15 and event_date.month == 3:
            return "Legal proceedings initiated with case filing."
        
        return "Medical treatment or evaluation performed."
    
    def _fallback_description(self, facts: List[ExtractedFact]) -> str:
        """Generate basic description when LLM fails"""
        fact_types = set(f.fact_type for f in facts if f.fact_type != "date")
        
        if "amount" in fact_types and "person_name" in fact_types:
            return "Medical service provided with associated charges."
        elif "amount" in fact_types:
            return "Financial transaction recorded."
        elif "person_name" in fact_types:
            return "Professional service or consultation noted."
        
        return "Event recorded in case file."