'''Model for an intermediate representation of the medical questionnaire diagram'''

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

@dataclass
class DiagramElement:
    """Base class for all diagram elements"""
    id: str
    element_type: str
    visual_properties: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, str] = field(default_factory=dict)

@dataclass
class DiagramNode(DiagramElement):
    """Represents a node in the intermediate representation"""
    label: str = ""
    parent_id: Optional[str] = None
    geometry: Dict[str, float] = field(default_factory=dict)

@dataclass
class DiagramEdge(DiagramElement):
    """Represents an edge in the intermediate representation"""
    source: str
    target: str
    label: str = ""

@dataclass
class DiagramContainer(DiagramElement):
    """Represents a container in the intermediate representation"""
    heading: str = ""
    contained_elements: List[str] = field(default_factory=list)

@dataclass
class Diagram:
    """Top-level container for the intermediate representation"""
    nodes: Dict[str, DiagramNode] = field(default_factory=dict)
    edges: Dict[str, DiagramEdge] = field(default_factory=dict)
    containers: Dict[str, DiagramContainer] = field(default_factory=dict)
