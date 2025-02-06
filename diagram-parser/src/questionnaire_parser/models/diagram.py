from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class NodeType(str, Enum):
    SELECT_ONE = "select_one"
    SELECT_MULTIPLE = "select_multiple"
    NOTE = "note"
    CALCULATE = "calculate"
    CONTAINER_PAGE = "container_page"
    GOTO = "goto"
    RHOMBUS = "rhombus"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    FLAG = "flag"

class Severity(str, Enum):
    NONE = "none"
    BENIGN = "green"
    MODERATE = "yellow"
    SEVERE = "red"

class GeometryModel(BaseModel):
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0

class DiagramElement(BaseModel):
    id: str
    element_type: str
    visual_properties: Dict[str, str] = Field(default_factory=dict)
    attributes: Dict[str, str] = Field(default_factory=dict)

class DiagramNode(DiagramElement):
    node_type: NodeType
    label: str = ""
    parent_id: Optional[str] = None
    geometry: GeometryModel = Field(default_factory=GeometryModel)
    is_diagnosis: bool = False
    severity: Severity = Severity.NONE
    help_text: Optional[str] = None
    hint_text: Optional[str] = None
    container_type: Optional[str] = None
    container_id: Optional[str] = None

class SelectOption(BaseModel):
    label: str
    value: str
    parent_id: str

class DiagramEdge(DiagramElement):
    source: str
    target: str
    label: str = ""
    condition: Optional[Dict] = None  # For storing edge logic

class DiagramContainer(DiagramElement):
    heading: str = ""
    contained_elements: List[str] = Field(default_factory=list)
    container_type: str  # Either "page" or "hint_media"

class Diagram(BaseModel):
    nodes: Dict[str, DiagramNode] = Field(default_factory=dict)
    edges: Dict[str, DiagramEdge] = Field(default_factory=dict)
    containers: Dict[str, DiagramContainer] = Field(default_factory=dict)
    select_options: Dict[str, SelectOption] = Field(default_factory=dict)
