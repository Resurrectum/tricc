"""
Data model for medical questionnaires as represented in draw.io diagrams.

This module defines the structure and validation rules for medical questionnaires
that are designed using draw.io. It handles the specific way draw.io represents
different question types, calculation nodes, and diagnostic elements through
shapes, styles, and connections. The model includes validation rules that ensure
the diagram follows the expected conventions for medical questionnaire design
in draw.io.

The model preserves draw.io-specific elements like geometry and style information,
as these are essential for validating that the diagram correctly represents
different node types through visual properties. For example, hexagonal shapes
represent integer inputs, while ellipses represent decimal inputs.

While this model is used as part of a system for processing medical questionnaires,
it specifically deals with the draw.io representation stage, before any
transformation into other formats like NetworkX graphs or HTML forms.

In short: this module provides a data model for all elements that can exist in a valid 
draw.io diagram that represents a medical questionnaire.
"""

from typing import List
from enum import Enum
from pydantic import BaseModel, validator
from questionnaire_parser.models.diagram import Diagram, NodeType, DiagramNode

class NodeValidationError(Exception):
    pass


class NodeType(str, Enum):
    """Enumeration of possible node types in the medical questionnaire"""
    SELECT_ONE = "select_one"
    SELECT_MULTIPLE = "select_multiple"
    NOTE = "note"
    CALCULATE = "calculate"
    DIAGNOSIS = "diagnosis"
    INTEGER = "integer"
    DECIMAL = "decimal"
    TEXT = "text"
    GOTO = "goto"
    RHOMBUS = "rhombus"
    CONTAINER_PAGE = "container_page"
    CONTAINER_HINT_MEDIA = "container_hint_media"
    HELP = "help"
    HINT = "hint"

class DiagnosisSeverity(str, Enum):
    """Severity levels for diagnosis nodes"""
    SEVERE = "severe"
    MODERATE = "moderate"
    BENIGN = "benign"
    NONE = "none"


class Node(BaseElement):
    """Represents a node in the diagram
    
    While BaseElement provides the raw draw.io properties,
    this class interprets those properties into domain concepts:
    - For help nodes, the 'label' becomes 'help_text'
    - For hint nodes, the 'label' becomes 'hint_text'
    - For numeric nodes, the 'label' is parsed to determine 'value_type'
    """
    # These are interpretations of the physical properties:
    node_type: NodeType           # Interpreted from the shape/style
    is_diagnosis: bool = False    # Interpreted from the type and color
    severity: Optional[DiagnosisSeverity] = None  # Interpreted from the color
    
    # These are additional interpreted meanings of the 'label':
    help_text: Optional[str] = None     # When it's a help node
    hint_text: Optional[str] = None     # When it's a hint node
    value_type: Optional[str] = None    # When it's a numeric node
    
    # These are structural relationships:
    parent_id: Optional[str] = None
    container_id: Optional[str] = None # ID of the container this node belongs to
    options: List[SelectOption] = Field(default_factory=list) # For select-type nodes
    
    @validator('node_type')
    @classmethod
    def validate_node_type_consistency(cls, v, values):
        """Validate that node properties are consistent with its type"""
        style = values.get('style')
        if not style:
            return v

        # Validate shape consistency with node type
        if v in [NodeType.INTEGER, NodeType.DECIMAL] and style.shape not in ['hexagon', 'ellipse']:
            raise ValueError(f"Invalid shape for {v} node type")
        
        return v

    @validator('help_text', 'hint_text', 'value_type')
    @classmethod
    def interpret_label(cls, v, values):
        """
        Interprets the base label field based on the node type.
        This ensures we properly translate the raw draw.io label
        into the appropriate domain-specific field.
        """
        node_type = values.get('node_type')
        label = values.get('label')
        
        if node_type == NodeType.HELP:
            return label
        # ... similar logic for other types


    @mode_validator(mode='after')
    @classmethod
    def validate_node_structure(cls, values):
        """Validate overall node structure based on its type"""
        node_type = values.get('node_type')
        options = values.get('options', [])

        if node_type in [NodeType.SELECT_ONE, NodeType.SELECT_MULTIPLE] and not options:
            raise ValueError(f"{node_type} nodes must have at least one option")

        if node_type in [NodeType.INTEGER, NodeType.DECIMAL] and not values.get('value_type'):
            values['value_type'] = 'int' if node_type == NodeType.INTEGER else 'float'

        return values
    


class SelectOption(BaseModel):
    """Represents a user choice option in a select-type question"""
    label: str
    value: str
    edge_logic: Optional[str] = None

    @validator('label', 'value')
    @classmethod
    def validate_non_empty(cls, v):
        """Ensure required fields are not empty"""
        if not v or not v.strip():
            raise ValueError("Required fields cannot be empty")
        return v.strip()


class Container(BaseElement):
    """Represents a container element in the diagram"""
    container_type: str
    contained_elements: List[str] = Field(default_factory=list)
    heading: Optional[str] = None

    @validator('container_type')
    @classmethod
    def validate_container_type(cls, v):
        """Validate container type"""
        valid_types = ['page', 'hint_media']
        if v not in valid_types:
            raise ValueError(f"Container type must be one of: {valid_types}")
        return v




class NodeRules(BaseModel):
    diagram: Diagram

    @validator("diagram")
    @classmethod
    def validate_unique_ids(cls, v: Diagram) -> Diagram:
        node_ids = set()
        for node_id in v.nodes:
            if node_id in node_ids:
                raise NodeValidationError(f"Duplicate node ID found: {node_id}")
            node_ids.add(node_id)
        return v

    @validator("diagram")
    @classmethod
    def validate_required_attributes(cls, v: Diagram) -> Diagram:
        for node_id, node in v.nodes.items():
            if node.node_type in [NodeType.SELECT_ONE, NodeType.SELECT_MULTIPLE, 
                                NodeType.INTEGER, NodeType.DECIMAL, NodeType.RHOMBUS]:
                if not node.label:
                    raise NodeValidationError(f"Node {node_id} missing required label")
        return v

    @validator("diagram")
    @classmethod
    def validate_select_options(cls, v: Diagram) -> Diagram:
        for node_id, node in v.nodes.items():
            if node.node_type in [NodeType.SELECT_ONE, NodeType.SELECT_MULTIPLE]:
                options = [opt for opt in v.select_options.values() 
                          if opt.parent_id == node_id]
                if not options:
                    raise NodeValidationError(
                        f"Select node {node_id} has no options")
        return v

    @validator("diagram")
    @classmethod
    def validate_rhombus_references(cls, v: Diagram) -> Diagram:
        for node_id, node in v.nodes.items():
            if node.node_type == NodeType.RHOMBUS:
                reference_id = node.attributes.get("reference_node")
                if not reference_id:
                    raise NodeValidationError(
                        f"Rhombus {node_id} missing reference node")
                if reference_id not in v.nodes:
                    raise NodeValidationError(
                        f"Rhombus {node_id} references non-existent node")
                ref_node = v.nodes[reference_id]
                if not cls._is_valid_rhombus_reference(ref_node):
                    raise NodeValidationError(
                        f"Invalid rhombus reference type for node {node_id}")
        return v

    @staticmethod
    def _is_valid_rhombus_reference(node: DiagramNode) -> bool:
        valid_reference_types = {
            NodeType.SELECT_ONE,
            NodeType.SELECT_MULTIPLE,
            NodeType.INTEGER,
            NodeType.DECIMAL,
            NodeType.FLAG
        }
        return node.node_type in valid_reference_types


