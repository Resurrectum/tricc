'''Custom exceptions for parsing draw.io xml files.'''
from datetime import datetime

class XMLParsingError(Exception):
    """Raised when there is an error parsing the XML file"""

class NodeValidationError(Exception):
    """Raised when there is an error validating a node"""

class DiagramValidationError(Exception):
    """Base exception for diagram validation errors"""
    def __init__(self, message: str, element_id: str):
        self.element_id = element_id
        self.timestamp = datetime.now()
        super().__init__(f"{message} (Element ID: {element_id})")

class EdgeValidationError(ValueError):
    """Base class for edge validation errors."""
    def __init__(self, message, element_id=None, details=None):
        self.element_id = element_id  # ID of the problematic element
        self.details = details or {}   # Additional context for debugging
        super().__init__(message)

class MissingEndpointsError(EdgeValidationError):
    """Raised when both endpoints are missing."""
    def __init__(self, message, element_id=None, details=None):
        super().__init__(message, element_id, details)
        self.field_name = "endpoints"  # Specific field that has the problem
