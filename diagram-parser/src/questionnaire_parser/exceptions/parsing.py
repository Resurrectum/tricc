class XMLParsingError(Exception):
    """Raised when there is an error parsing the XML file"""
    pass

class NodeValidationError(Exception):
    """Raised when there is an error validating a node"""
    pass