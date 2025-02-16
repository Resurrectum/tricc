"""
Data model for a diagram without any specific format
"""

from enum import Enum
from typing import Dict, List, Optional, Union, Set
from logging import getLogger
from pydantic import BaseModel, Field, validator, model_validator, root_validator
from uuid import UUID
from questionnaire_parser.utils.logging import setup_logger
from questionnaire_parser.exceptions.validation import (
    NodeValidationError, EdgeValidationError, ContainerValidationError)

logger = getLogger(__name__)

class Geometry(BaseModel):
    """Geometric properties of a non-edge diagram element"""
    x: float = Field(default=0.0, description="X coordinate")
    y: float = Field(default=0.0, description="Y coordinate")
    width: float = Field(default=0.0, description="Width of the element")
    height: float = Field(default=0.0, description="Height of the element")

    @validator('width', 'height')
    @classmethod
    def validate_positive_dimensions(cls, v):
        """Ensure dimensions are positive numbers"""
        if v < 0:
            raise ValueError("Dimensions must be positive numbers")
        return v

class ShapeType(str, Enum):
    """Enumeration of possible shapes for nodes"""
    RECTANGLE = "rectangle"
    HEXAGON = "hexagon"
    ELLIPSE = "ellipse"
    RHOMBUS = "rhombus"
    CALLOUT = "callout"
    OFFPAGE = "offPageConnector"
    LIST = "list" # Multiple choice nodes


class Style(BaseModel):
    """Visual style properties of a diagram element"""
    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None
    rounded: bool = False
    dashed: bool = False

    @validator('fill_color', 'stroke_color')
    @classmethod
    def validate_color_format(cls, v):
        """Validate color format if present"""
        if v and not v.startswith('#'):
            v = f"#{v}"
        return v

class NumericConstraints(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    constraint_message: Optional[str] = None

class ElementMetadata(BaseModel):
    """Non-visual information attached to elements (tags)"""
    name: Optional[str] = None  # The 'name' attribute, used differently by different node types
    numeric_constraints: Optional[NumericConstraints] = None  # for hexagon/ellipse nodes

class BaseElement(BaseModel):
    """Base class for all diagram elements. 
    This is the base for the three possible types of elements: 
    nodes, edges, and containers."""
    id: str
    label: str = ""
    page_id: str = "" # ID of the page containing the element
    metadata: Optional[ElementMetadata] = None  # Store non-visual information here

    @validator('id')
    @classmethod
    def validate_id_format(cls, v):
        """Ensure ID is not empty and has valid format"""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()

class Node(BaseElement):
    """Represents a node in the diagram. At this basic structural level,
    a node is simply an element with a position, label and shape. But a list node
    can have one or more options."""
    shape: ShapeType
    geometry: Geometry
    style: Style
    options: Optional[List[str]] = None # Only for multiple choice nodes

    @validator('shape')
    @classmethod
    def validate_shape(cls, v):
        """Ensure shape is valid for a node"""
        return v

    @model_validator(mode='after')
    def validate_list_attributes(self):
        """Ensure non-list nodes don't have options"""
        if self.shape != ShapeType.LIST and self.options is not None:
            raise ValueError("Only list nodes can have options")

        # Validate rhombus has name
        if self.shape == ShapeType.RHOMBUS:
            if not self.metadata or not self.metadata.name:
                raise ValueError("Rhombus nodes must have a name to reference another node")

        return self

class Group(BaseElement):
    """Represents a group of elements in the diagram. 
    A group contains other elements.
    Beyond the base element properties, a group has a non-empty list 
    of contained elements (children)."""
    contained_elements: Set[str] = Field(default_factory=set)
    geometry: Geometry

class Edge(BaseElement):
    """Represents an edge in the diagram. Beyond the base element properties,
    an edge has a source and target node."""
    source: str # id of the source node
    target: str # id of the target node

    @validator('source', 'target')
    @classmethod
    def validate_edge_endpoints(cls, v, field):
        """Ensure edge endpoints are valid: 
        - they exist
        - source and target are different
        - source and target are not other edges"""
        if not v or not v.strip():
            logger.warning(f"Edge {field.name} validation failed: endpoint cannot be empty")
            raise ValueError("Edge endpoints cannot be empty")
        return v.strip()
    
    @root_validator(pre=True)
    @classmethod
    def validate_edge_structure(cls, values):
        """Validate edge structure"""
        source = values.get('source')
        target = values.get('target')

        if source and target:
            if source == target:
                raise ValueError("Edge cannot connect a node to itself")

        # Additional validations could go here
        # Note: We might need to pass the diagram context to do some of these checks
        return values

class Diagram(BaseModel):
    """Top-level container for the entire diagram"""
    nodes: Dict[str, Node] = Field(default_factory=dict)
    edges: Dict[str, Edge] = Field(default_factory=dict)
    groups: Dict[str, Group] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_diagram_structure(self) -> 'Diagram':
        """Validate overall diagram structure"""
        # Validate edge connections
        for edge_id, edge in self.edges.items():
            if edge.source not in self.nodes:
                raise ValueError(f"Edge {edge_id} references non-existent source node")
            if edge.target not in self.nodes:
                raise ValueError(f"Edge {edge_id} references non-existent target node")

        # Validate group memberships
        for group_id, group in self.groups.items():
            if not group.contained_elements:
                raise ValueError(f"Group {group_id} must contain at least one element")
            for element_id in group.contained_elements:
                if element_id not in self.nodes:
                    raise ValueError(f"Group {group_id} claims to contain a node that doesn't exist in the diagram.")

        # Validate list nodes have options
        for node_id, node in self.nodes.items():
            if node.shape == ShapeType.LIST and not node.options:
                raise ValueError(f"List node {node_id} must have at least one option")

        # Validate rhombus references
        for node_id, node in self.nodes.items():
            if node.shape == ShapeType.RHOMBUS:
                if not node.metadata.name:  # The referenced node should be in the name field
                    raise ValueError(f"Rhombus node {node_id} must reference another node")
                if node.metadata.name not in self.nodes.values().metadata.name:
                    raise ValueError(f"Rhombus node {node_id} references non-existent node {node.metadata.name}")
                
                # According to docs, referenced node must be upstream
                # However, we might need the actual graph structure to validate this
                # Could be added later when we have the complete DAG

        return self

    def get_entry_points(self) -> List[str]:
        """Find all nodes that could be entry points (no incoming edges)"""
        incoming_edges = {edge.target for edge in self.edges.values()}
        return [node_id for node_id in self.nodes.keys() if node_id not in incoming_edges]

    def validate_dag(self) -> bool:
        """Verify that the graph is a valid DAG (no cycles)"""
        visited = set()
        path = set()

        def dfs(node_id: str) -> bool:
            if node_id in path:
                return False
            if node_id in visited:
                return True

            path.add(node_id)
            visited.add(node_id)

            # Check all outgoing edges
            for edge in self.edges.values():
                if edge.source_id == node_id:
                    if not dfs(edge.target):
                        return False

            path.remove(node_id)
            return True

        # Check from all possible entry points
        for entry_point in self.get_entry_points():
            if not dfs(entry_point):
                return False

        return True
