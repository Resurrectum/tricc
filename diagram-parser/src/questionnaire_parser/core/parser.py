import html
from typing import Dict, Optional
from lxml import etree as ET
from logging import getLogger
from pathlib import Path
import json
from pydantic import ValidationError

from questionnaire_parser.models.diagram import (
    Diagram,
    Node,
    SelectOption,
    Edge,
    Group,
    Geometry,
    Style,
    ShapeType,
    ElementMetadata,
    NumericConstraints,
)
from questionnaire_parser.exceptions.parsing import (
    XMLParsingError,
    MissingEndpointsError,
)
from questionnaire_parser.utils.validation import (
    ValidationCollector,
    ValidationLevel,
    ValidationSeverity,
)

from questionnaire_parser.utils.validation_messages import EdgeValidationMessage
from questionnaire_parser.utils.edge_error_handler import EdgeValidationErrorHandler

logger = getLogger(__name__)


class DrawIoParser:
    """Parser for converting draw.io XML files into our diagram model."""

    def __init__(
        self,
        validation_level: ValidationLevel = ValidationLevel.NORMAL,
        externals_path: Path = Path("externals.json"),
    ):
        """Initialize parser with empty diagram and no namespace."""
        self.ns = None  # no namespace in draw.io XML
        self.validator = ValidationCollector(validation_level)
        self.diagram = Diagram(validation_collector=self.validator)
        self.edge_error_handler = EdgeValidationErrorHandler(self.validator)
        # Load external data
        try:
            with externals_path.open("r") as f:
                self.allowed_externals = set(json.load(f).get("allowed_externals", []))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.validator.add_result(
                severity=ValidationSeverity.WARNING,
                message=f"Failed to load externals from {externals_path}: {e}. Assuming empty set.",
                element_type="Parser",
            )
            self.allowed_externals = set()

    def parse_file(
        self, filepath: Path
    ) -> tuple[Optional[Diagram], ValidationCollector]:
        """Parse a draw.io XML file into our diagram model.

        Args:
            filepath: Path to the draw.io XML file

        Returns:
            Tuple of (Diagram, ValidationCollector)
        """
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            # Save validation report
            report_path = Path(filepath).parent / "validation_reports"
            report_path.mkdir(exist_ok=True)

            # Parse the diagram
            diagram = self.parse_xml(root)
            # Save the report after parsing is complete
            self.validator.save_report(report_path / "parsing_validation.log")

            return diagram, self.validator

        except ET.ParseError as e:
            message = f"Failed to parse XML file: {e}"
            if self.validator:
                self.validator.add_result(
                    severity=ValidationSeverity.CRITICAL,
                    message=message,
                    element_type="XML",
                )
                # Save report
                self.validator.save_report(report_path / "parsing_validation.log")
                return None, self.validator

            raise ET.ParseError(message)  # raise immediately if no collector

        except Exception as e:  # all other exceptions
            message = f"Unexpected error during parsing: {str(e)}"
            if self.validator:
                self.validator.add_result(
                    severity=ValidationSeverity.CRITICAL,
                    message=message,
                    element_type="Parsing",
                )
                # Save report
                self.validator.save_report(report_path / "parsing_validation.log")
                return diagram, self.validator
            raise Exception(message)

    def parse_xml(self, root: ET.Element) -> Diagram:
        """Parse XML content into diagram model"""
        # First pass: Create all groups
        self._parse_groups(root)

        # Second pass: Create list nodes (multiple choice questions)
        self._parse_list_nodes(root)

        # Third pass: Create regular nodes (including rhombus)
        self._parse_nodes(root)

        # Fourth pass: Create edges
        self._parse_edges(root)

        # Validate diagram structure after parsing
        validated_diagram = Diagram.model_validate(self.diagram)

        return validated_diagram

    def _parse_groups(self, root: ET.Element):
        """First pass: Parse group elements"""
        for cell in root.iter("mxCell"):
            if self._is_group(cell):
                group = self._create_group(cell)
                self.diagram.groups[group.id] = group
                # Validate diagram structure after each group is added

    def _parse_list_nodes(self, root: ET.Element):
        """Second pass: Parse list nodes (multiple choice)"""
        for cell in root.iter("mxCell"):
            if self._is_list_node(cell):
                node = self._create_list_node(cell)
                self.diagram.nodes[node.id] = node

                # Add to parent group if applicable
                parent_id = cell.get("parent")
                if parent_id in self.diagram.groups:
                    self.diagram.groups[parent_id].contained_elements.add(node.id)

    def _parse_nodes(self, root: ET.Element):
        """Third pass: Parse regular nodes (including rhombus)"""
        for cell in root.iter("mxCell"):
            if self._is_node(cell):
                # Skip if already processed as list node
                base_attrs = self._extract_base_attributes(cell)
                if base_attrs["id"] in self.diagram.nodes:
                    continue

                # Check if this is a select option for a list node
                parent_id = cell.get("parent")
                if parent_id in self.diagram.nodes:
                    parent_node = self.diagram.nodes[parent_id]
                    if parent_node.shape == ShapeType.LIST:
                        self._add_option_to_list(parent_node, cell)
                        continue

                # Create regular node
                node = self._create_node(cell)
                self.diagram.nodes[node.id] = node

                # Add to parent group if applicable
                if parent_id in self.diagram.groups:
                    self.diagram.groups[parent_id].contained_elements.add(node.id)

    def _parse_edges(self, root: ET.Element):
        """Fourth pass: Parse edges"""
        for cell in root.iter("mxCell"):
            if self._is_edge(cell):
                edge = self._create_edge(cell)
                if edge:  # Only add if created successfully
                    self.diagram.edges[edge.id] = edge

    def _is_group(self, cell: ET.Element) -> bool:
        """Check if cell represents a group"""
        if cell.get("vertex") != "1":
            return False
        style = self._parse_style_string(cell.get("style", ""))
        return "swimlane" in style and "childLayout" not in style

    def _is_list_node(self, cell: ET.Element) -> bool:
        """Check if cell represents a list node"""
        if cell.get("vertex") != "1":
            return False
        style = self._parse_style_string(cell.get("style", ""))
        return "swimlane" in style and style.get("childLayout") == "stackLayout"

    def _is_node(self, cell: ET.Element) -> bool:
        """Check if cell represents a regular node"""
        return (
            cell.get("vertex") == "1"
            and not self._is_group(cell)
            and not self._is_list_node(cell)
        )

    def _is_edge(self, cell: ET.Element) -> bool:
        """Check if cell represents an edge"""
        return cell.get("edge") == "1"

    def _extract_base_attributes(self, cell: ET.Element) -> Dict[str, str]:
        """Extract base attributes (id, label, page_id) from a cell element.

        If the cell is wrapped in a UserObject/object element, extracts attributes
        from the wrapper. Otherwise extracts from the cell itself.

        Args:
            cell: The mxCell element to extract attributes from

        Returns:
            Dictionary containing 'id', 'label', and 'page_id'
        """
        wrapper = cell.getparent()
        if wrapper.tag in ("UserObject", "object"):
            return {
                "id": wrapper.get("id"),
                "label": html.unescape(wrapper.get("label", "")),
                "page_id": self._get_page_id(cell),
            }
        else:
            return {
                "id": cell.get("id"),
                "label": html.unescape(cell.get("value", "")),
                "page_id": self._get_page_id(cell),
            }

    def _get_element_label(
        self, element_id: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Get the label and type of an element by its ID, handling all element types.

        Args:
            element_id: ID of the element to look up

        Returns:
            A tuple of (label, element_type) where:
            - label is the text label of the element if found, None otherwise
            - element_type is a string describing the type ('node', 'group', 'list', 'option', etc.)
        """
        if not element_id:
            return None, None

        # Check if it's a node
        if element_id in self.diagram.nodes:
            node = self.diagram.nodes[element_id]
            node_type = "list" if node.shape == ShapeType.LIST else "node"
            return node.label, node_type

        # Check if it's a select option (needs to search through list nodes)
        for node in self.diagram.nodes.values():
            if node.options:
                for option in node.options:
                    if option.id == element_id:
                        # Return both the option label and its parent list node's label
                        parent_info = f" (option of '{node.label}')"
                        return option.label + parent_info, "option"

        # Check if it's a group
        if element_id in self.diagram.groups:
            group = self.diagram.groups[element_id]
            # Include information about contained elements
            num_elements = len(group.contained_elements)
            elements_info = f" (group with {num_elements} elements)"
            return group.label + elements_info, "group"

        # Element not found
        return None, None

    def _create_group(self, cell: ET.Element) -> Group:
        """Create a Group from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        metadata = self._extract_metadata(cell)
        return Group(
            id=base_attrs["id"],
            label=base_attrs["label"],
            page_id=base_attrs["page_id"],
            metadata=metadata,
            geometry=self._create_geometry(cell),
            contained_elements=set(),  # Will be populated when processing nodes
        )

    def _create_list_node(self, cell: ET.Element) -> Node:
        """Create a List node from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        metadata = self._extract_metadata(cell)
        return Node(
            id=base_attrs["id"],
            label=base_attrs["label"],
            page_id=base_attrs["page_id"],
            metadata=metadata,
            shape=ShapeType.LIST,
            geometry=self._create_geometry(cell),
            style=self._create_style(cell),
            options=[],  # Will be populated when processing child nodes
        )

    def _create_node(self, cell: ET.Element) -> Node:
        """Create a regular Node from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        shape = self._determine_shape(cell)
        metadata = self._extract_metadata(cell)

        # Add numeric constraints for hexagon/ellipse nodes
        if shape in (ShapeType.HEXAGON, ShapeType.ELLIPSE):
            numeric_constraints = self._extract_numeric_constraints(cell)
            if metadata:
                metadata.numeric_constraints = numeric_constraints

        # Check for external rhombus
        external = False
        if shape == ShapeType.RHOMBUS and metadata and metadata.name:
            if metadata.name in self.allowed_externals:
                external = True

        return Node(
            id=base_attrs["id"],
            label=base_attrs["label"],
            page_id=base_attrs["page_id"],
            metadata=metadata,
            shape=shape,
            geometry=self._create_geometry(cell),
            style=self._create_style(cell),
            external=external,
        )

    def _create_select_option(self, cell: ET.Element) -> SelectOption:
        """Create a SelectOption object from cell element"""
        base_attrs = self._extract_base_attributes(cell)

        return SelectOption(
            id=base_attrs["id"],
            label=base_attrs["label"],
            page_id=base_attrs["page_id"],
            parent_id=cell.get("parent"),
            geometry=self._create_geometry(cell),
            style=self._create_style(cell),
        )

    def _create_edge(self, cell: ET.Element) -> Optional[Edge]:
        """Create an Edge from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        metadata = self._extract_metadata(cell)
        # pass diagram to the edge error handler
        self.edge_error_handler.set_diagram(self.diagram)

        try:
            return Edge(
                id=base_attrs["id"],
                label=base_attrs["label"],
                page_id=base_attrs["page_id"],
                metadata=metadata,
                source=cell.get("source"),
                target=cell.get("target"),
                # need this for managing flexible validations
                # validation_collector = self.validator
            )
        except ValidationError as ve:
            # Error handling done by EdgeValidationErrorHandler
            self.edge_error_handler.handle_edge_error(ve)

            return None

        except Exception as e:
            print(f"Unknown edge validation error: {e}")
            return None

    def _determine_shape(self, cell: ET.Element) -> ShapeType:
        """Determine shape type from cell style"""
        style = self._parse_style_string(cell.get("style", ""))

        for shape_type in ShapeType:
            # Skip list and rectangle as they are not stored as at all in the style dict
            if shape_type in (ShapeType.LIST, ShapeType.RECTANGLE):
                continue

            # 'ellipse' and 'rhombus' are stored as a key in the style dict
            if shape_type in style.keys():
                return shape_type
            elif style.get("shape") == shape_type:
                return shape_type
        # If not specific shape is found, it's rectangle
        return ShapeType.RECTANGLE

    def _add_option_to_list(self, list_node: Node, option_cell: ET.Element):
        """Add an option to a list node"""
        if not list_node.options:
            list_node.options = []
        select_option = self._create_select_option(option_cell)
        list_node.options.append(select_option)
        # Sort the options by the `y` value of their `Geometry` attribute to match draw.io order
        list_node.options.sort(key=lambda option: option.geometry.y)

    def _extract_metadata(self, cell: ET.Element) -> Optional[ElementMetadata]:
        """Extract metadata from cell or its parent UserObject"""
        # Check for parent UserObject/object
        parent = cell.getparent()
        if parent is not None and parent.tag in ("UserObject", "object"):
            return ElementMetadata(
                name=parent.get("name"),
                # Add other metadata extraction as needed
            )
        return None

    def _extract_numeric_constraints(
        self, cell: ET.Element
    ) -> Optional[NumericConstraints]:
        """Extract numeric constraints for hexagon/ellipse nodes"""
        parent = cell.getparent()
        if parent is not None and parent.tag in ("UserObject", "object"):
            return NumericConstraints(
                min_value=(
                    float(parent.get("min_value")) if parent.get("min_value") else None
                ),
                max_value=(
                    float(parent.get("max_value")) if parent.get("max_value") else None
                ),
                constraint_message=parent.get("constraint_message"),
            )
        return None

    def _create_geometry(self, cell: ET.Element) -> Geometry:
        """Create Geometry from cell"""
        geometry = cell.find("mxGeometry")
        if geometry is not None:
            return Geometry(
                x=float(geometry.get("x", 0)),
                y=float(geometry.get("y", 0)),
                width=float(geometry.get("width", 0)),
                height=float(geometry.get("height", 0)),
            )
        return Geometry()

    def _create_style(self, cell: ET.Element) -> Style:
        """Create Style from cell"""
        style_dict = self._parse_style_string(cell.get("style", ""))
        return Style(
            fill_color=style_dict.get("fillColor"),
            stroke_color=style_dict.get("strokeColor"),
            rounded=style_dict.get("rounded", "0") == "1",
            dashed=style_dict.get("dashed", "0") == "1",
        )

    def _parse_style_string(self, style_str: str) -> Dict[str, str]:
        """Parse draw.io style string into dictionary"""
        style_dict = {}
        if style_str:
            for item in style_str.split(";"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    style_dict[key.strip()] = value.strip()
                else:
                    style_dict[item] = ""

        return style_dict

    def _get_page_id(self, cell: ET.Element) -> str:
        """Get page ID for element"""
        # Walk up the tree to find the parent page
        current = cell
        while current is not None:
            if current.tag == "diagram":
                return current.get("id", "")
            current = current.getparent()
        return ""
