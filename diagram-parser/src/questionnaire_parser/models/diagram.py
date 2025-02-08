"""
Data model for a diagram without any specific format
"""

from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator, model_validator
from uuid import UUID
from questionnaire_parser.exceptions.validation import (
    NodeValidationError, EdgeValidationError, ContainerValidationError)


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


class Style(BaseModel):
    """Visual style properties of a diagram element"""
    shape: Optional[ShapeType] = None
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

class BaseElement(BaseModel):
    """Base class for all diagram elements. 
    This is the base for the three possible types of elements: 
    nodes, edges, and containers."""
    id: str
    geometry: Optional[Geometry] = None # Edges don't have geometry
    style: Style
    label: str = ""
    page_id: str = "" # ID of the page containing the element

    @validator('id')
    @classmethod
    def validate_id_format(cls, v):
        """Ensure ID is not empty and has valid format"""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()

class Node(BaseElement):
    """Represents a node in the diagram. At this basic structural level,
    a node is simply an element with a position, shape, and label."""
    pass

class Container(BaseElement):
    """Represents a container element in the diagram. 
    A container is a grouping element that can contain other elements.
    Beyond the base element properties, a container has a non-empty list 
    of contained elements (children)."""
    contained_elements: List[str] = Field(default_factory=list)

    @validator('container_type')
    @classmethod
    def validate_contained_elements(cls, v):
        """Validate that the container has at least one child element"""
        if not v:
            raise ValueError("Container must contain at least one element")
        return v

class Edge(BaseElement):
    """Represents an edge in the diagram. Beyond the base element properties,
    an edge has a source and target node."""
    source: str # id of the source node
    target: str # id of the target node

    @validator('source', 'target')
    @classmethod
    def validate_edge_endpoints(cls, v):
        """Ensure edge endpoints are valid: 
        - they exist
        - source and target are different
        - source and target are not other edges"""
        if not v or not v.strip():
            raise ValueError("Edge endpoints cannot be empty")
        return v.strip()
    
    @model_validator
    def validate_edge_structure(cls, values):
        """Validate edge structure"""
        source_id = values.get('source_id')
        target_id = values.get('target_id')

        if source_id and target_id:
            if source_id == target_id:
                raise ValueError("Edge cannot connect to itself")

            # Additional validations you suggested could go here
            # Note: We might need to pass the diagram context to do some of these checks    
        return values

    @model_validator
    @classmethod
    def validate_edge_structure(cls, values):
        """Validate edge does not connect to itself"""
        source = values.get('source') # source_id
        target = values.get('target') # target_id
        
        if source and target and source == target:
            raise ValueError("Edge cannot connect a node to itself")
            
        return values

class Diagram(BaseModel):
    """Top-level container for the entire diagram"""
    nodes: Dict[str, Node] = Field(default_factory=dict)
    edges: Dict[str, Edge] = Field(default_factory=dict)
    containers: Dict[str, Container] = Field(default_factory=dict)

    @model_validator(mode='after')
    @classmethod
    def validate_diagram_structure(cls, values):
        """Validate overall diagram structure"""
        nodes = values.get('nodes', {})
        edges = values.get('edges', {})
        containers = values.get('containers', {})

        # Validate edge connections
        for edge_id, edge in edges.items():
            if edge.source_id not in nodes:
                raise ValueError(f"Edge {edge_id} references non-existent source node")
            if edge.target_id not in nodes:
                raise ValueError(f"Edge {edge_id} references non-existent target node")

        # Validate container memberships
        for container_id, container in containers.items():
            for element_id in container.contained_elements:
                if element_id not in nodes:
                    raise ValueError(f"Container {container_id} references non-existent node")

        # Validate node relationships
        for node_id, node in nodes.items():
            if node.parent_id and node.parent_id not in nodes:
                logger.error(f"Node {node_id} references non-existent parent {node.parent_id}")
                raise NodeValidationError("Node references non-existent parent", node_id)
            if node.container_id and node.container_id not in containers:
                raise ValueError(f"Node {node_id} references non-existent container")

        return values

    def get_entry_points(self) -> List[str]:
        """Find all nodes that could be entry points (no incoming edges)"""
        incoming_edges = {edge.target_id for edge in self.edges.values()}
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
                    if not dfs(edge.target_id):
                        return False

            path.remove(node_id)
            return True

        # Check from all possible entry points
        for entry_point in self.get_entry_points():
            if not dfs(entry_point):
                return False

        return True
