class XMLParsingError(Exception):
    """Raised when there is an error parsing the XML file"""
    pass

class NodeValidationError(Exception):
    """Raised when there is an error validating a node"""
    pass

class DiagramValidationError(ValueError):
    """Base exception for diagram validation errors"""
    def __init__(self, message: str, element_id: str):
        self.element_id = element_id
        super().__init__(f"{message} (Element ID: {element_id})")

class EdgeValidationError(DiagramValidationError):
    """Raised when edge validation fails"""
    pass

class GroupValidationError(DiagramValidationError):
    """Raised when container validation fails"""
    pass