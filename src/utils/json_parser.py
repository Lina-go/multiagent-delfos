"""
JSON Parser utility for extracting JSON from LLM responses.
"""
import json
import re
from typing import Dict, Any


class JSONParser:
    """Helper class to extract clean JSON from LLM responses."""
    
    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """Attempts to extract a JSON block from text."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            return {}

