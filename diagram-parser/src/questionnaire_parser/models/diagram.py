"""
Data model for a diagram without any specific format
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Union
from pydantic import (
    BaseModel,
    Field,
    validator,
    model_validator,
)
from pydantic_core import PydanticCustomError
from questionnaire_parser.utils.validation import (
    ValidationCollector,
    ValidationSeverity,
)
from questionnaire_parser.exceptions.parsing import MissingEndpointsError
from questionnaire_parser.business_rules.external_flags import ExternalReferences


class Geometry(BaseModel):
    """Geometric properties of a non-edge diagram element"""

    x: float = Field(default=0.0, description="X coordinate")
    y: float = Field(default=0.0, description="Y coordinate")
    width: float = Field(default=0.0, description="Width of the element")
    height: float = Field(default=0.0, description="Height of the element")

    @validator("width", "height")
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
    LIST = "list"  # Multiple choice nodes


class Style(BaseModel):
    """Visual style properties of a diagram element"""

    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None
    rounded: bool = False
    dashed: bool = False

    @validator("fill_color", "stroke_color")
    @classmethod
    def validate_color_format(cls, v):
        """Validate color format if present"""
        if v and not v.startswith("#"):
            v = f"#{v}"
        return v


class NumericConstraints(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    constraint_message: Optional[str] = None


class ElementMetadata(BaseModel):
    """Non-visual information attached to elements (tags)"""

    name: Optional[str] = (
        None  # The 'name' attribute, used differently by different node types
    )
    numeric_constraints: Optional[NumericConstraints] = (
        None  # for hexagon/ellipse nodes
    )


class BaseElement(BaseModel):
    """Base class for all diagram elements.
    This is the base for the three possible types of elements:
    nodes, edges, and containers."""

    id: str
    label: str = ""
    page_id: str = ""  # ID of the page containing the element
    metadata: Optional[ElementMetadata] = None  # Store non-visual information here

    @validator("id")
    @classmethod
    def validate_id_format(cls, v):
        """Ensure ID is not empty and has valid format"""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()


class SelectOption(BaseElement):
    """Represents a select-option, which belongs to a list."""

    parent_id: str
    geometry: Geometry
    style: Style


class Node(BaseElement):
    """Represents a node in the diagram. At this basic structural level,
    a node is simply an element with a position, label and shape. But a list node
    can have one or more options."""

    shape: ShapeType
    geometry: Geometry
    style: Style
    options: Optional[List[SelectOption]] = None  # Only for multiple choice nodes

    @model_validator(mode="after")
    def validate_list_attributes(self):
        """Ensure non-list nodes don't have options"""
        if self.shape != ShapeType.LIST and self.options is not None:
            raise ValueError("Only list nodes can have options")

        # Validate rhombus has name
        if self.shape == ShapeType.RHOMBUS:
            if not self.metadata or not self.metadata.name:
                raise ValueError(
                    "Rhombus nodes must have a name to reference another node"
                )

        return self


class Group(BaseElement):
    """Represents a group of elements in the diagram.
    A group contains other elements.
    Beyond the base element properties, a group has a non-empty list
    of contained elements (children)."""

    contained_elements: Set[str] = Field(default_factory=set)
    geometry: Geometry


class Edge(BaseElement):
    """Represents an edge in the diagram.

    An edge must have at least one connection point (either source or target) to be
    considered valid. Edges missing both endpoints are invalid as they cannot be
    meaningfully displayed or used in the diagram. However, edges missing just one
    endpoint are allowed - their validity will be checked when adding them to the diagram.

    Attributes:
        source: ID of the source node. Can be missing if target exists.
        target: ID of the target node. Can be missing if source exists.
    """

    source: Optional[str] = None  # Making these optional allows single missing endpoint
    target: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode="after")
    def validate_endpoints(self) -> "Edge":
        """Ensures the edge has both endpoints, but distinguish between 3 cases:
        - source is missing and target is present
        - source is present and target is missing
        - source and target are missing.

        An edge with no endpoints is a 'ghost edge'. It cannot be meaningfully
        displayed or used.
        """
        source = getattr(self, "source", None)
        target = getattr(self, "target", None)

        if not source and target:  # only source is missing
            raise PydanticCustomError(
                "source-missing",
                "Edge has no source.",
                {"edge": self.id, "source": source},
            )
        if source and not target:  # only target is missing
            raise PydanticCustomError(
                "target-missing",
                "Edge has no target.",
                {"edge": self.id, "target": target},
            )
        if not source and not target:
            raise PydanticCustomError(
                "ghost-edge",  # error type
                "Ghost edge found where source and target are missing. Edge gets ignored.",  # message template
                {"edge": self.id},  # context
            )
        # if validation passes, return the edge
        return self


class Diagram(BaseModel):
    """Top-level container for the entire diagram"""

    nodes: Dict[str, Node] = Field(default_factory=dict)
    edges: Dict[str, Edge] = Field(default_factory=dict)
    groups: Dict[str, Group] = Field(default_factory=dict)
    validation_collector: Optional[ValidationCollector] = None
    allowed_externals: Optional[ExternalReferences] = ExternalReferences()

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode="after")
    def validate_structure(self) -> "Diagram":
        """Validate overall diagram structure"""
        # Precompute valid referral nodes (excluding rhombus nodes, including externals)
        valid_referral_nodes = {
            n.metadata.name
            for n in self.nodes.values()
            if n.metadata and n.metadata.name and n.shape != ShapeType.RHOMBUS
        } | self.allowed_externals.get_all_references()

        # Precompute valid source IDs
        valid_node_ids = {
            node_id
            for node_id, node in self.nodes.items()
            if node.shape != ShapeType.LIST
        }  # Exclude list nodes
        all_option_ids = {
            option.id
            for node in self.nodes.values()
            if node.shape == ShapeType.LIST and node.options
            for option in node.options
        }
        valid_source_ids = valid_node_ids | all_option_ids  # Union of valid sources

        group_ids = set(self.groups.keys())

        # Validate edge connections
        for edge_id, edge in self.edges.items():
            if edge.source:
                if edge.source in group_ids:
                    message = f"Edge '{edge_id}' has invalid source '{edge.source}' (a group)."
                    if self.validation_collector:
                        self.validation_collector.add_result(
                            severity=ValidationSeverity.ERROR,
                            message=message,
                            element_id=edge_id,
                            element_type="Edge",
                            field_name="source",
                        )
                    else:
                        raise ValueError(message)
                elif edge.source not in valid_source_ids:
                    message = f"Edge origins from an invalid source '{edge.source}'."
                    if self.validation_collector:
                        self.validation_collector.add_result(
                            severity=ValidationSeverity.ERROR,
                            message=message,
                            element_id=edge_id,
                            element_type="Edge",
                            field_name="source",
                        )
                    else:
                        raise ValueError(message)

        # Validate group memberships
        for group_id, group in self.groups.items():
            if not group.contained_elements:
                message = f"Group {group_id} must contain at least one element"
                if self.validation_collector:
                    self.validation_collector.add_result(
                        severity=ValidationSeverity.ERROR,
                        message=message,
                        element_id=group_id,
                        element_type="Group",
                    )
                else:
                    raise ValueError(message)

        # Validate list nodes have options
        for node_id, node in self.nodes.items():
            if node.shape == ShapeType.LIST and not node.options:
                message = f"List node {node_id} must have at least one option"
                if self.validation_collector:
                    self.validation_collector.add_result(
                        severity=ValidationSeverity.ERROR,
                        message=message,
                        element_id=node_id,
                        element_type="Node",
                        field_name="options",
                    )
                else:
                    raise ValueError(message)

        # Validate rhombus references
        for node_id, node in self.nodes.items():
            if node.shape == ShapeType.RHOMBUS:
                if not node.metadata or not node.metadata.name:
                    if self.validation_collector:
                        self.validation_collector.add_result(
                            severity=ValidationSeverity.ERROR,
                            message=f"Rhombus node {node_id} must reference another node",
                            element_id=node_id,
                            element_type="Node",
                            field_name="metadata.name",
                        )
                    else:
                        raise ValueError(message)
                elif not node.metadata.name not in valid_referral_nodes:
                    if self.validation_collector:
                        self.validation_collector.add_result(
                            severity=ValidationSeverity.ERROR,
                            message=f"Rhombus node {node_id} references non-existent node {node.metadata.name}",
                            element_id=node_id,
                            element_type="Node",
                            field_name="metadata.name",
                        )
                    else:
                        raise ValueError(message)

        return self

    def get_entry_points(self) -> List[str]:
        """Find all nodes that could be entry points (no incoming edges)"""
        incoming_edges = {edge.target for edge in self.edges.values()}
        return [
            node_id for node_id in self.nodes.keys() if node_id not in incoming_edges
        ]

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
