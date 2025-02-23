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

class EdgeValidationError(DiagramValidationError):
    """Raised when edge validation fails"""

class GroupValidationError(DiagramValidationError):
    """Raised when container validation fails"""
