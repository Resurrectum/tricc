# src/questionnaire_parser/exceptions/validation.py
class DiagramValidationError(ValueError):
    """Base exception for diagram validation errors"""
    def __init__(self, message: str, element_id: str):
        self.element_id = element_id
        super().__init__(f"{message} (Element ID: {element_id})")

class NodeValidationError(DiagramValidationError):
    """Raised when node validation fails"""
    pass

class EdgeValidationError(DiagramValidationError):
    """Raised when edge validation fails"""
    pass

class ContainerValidationError(DiagramValidationError):
    """Raised when container validation fails"""
    pass