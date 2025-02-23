from typing import Dict, Optional
from lxml import etree as ET
from logging import getLogger
from pathlib import Path
from pydantic import ValidationError

from questionnaire_parser.models.diagram import (
    Diagram, Node, Edge, Group, Geometry, Style, ShapeType,
    ElementMetadata, NumericConstraints
)
from questionnaire_parser.exceptions.parsing import XMLParsingError, DiagramValidationError, EdgeValidationError
from questionnaire_parser.utils.validation import ValidationCollector, ValidationLevel, ValidationSeverity

from questionnaire_parser.utils.validation_messages import EdgeValidationMessage

logger = getLogger(__name__)

class DrawIoParser:
    """Parser for converting draw.io XML files into our diagram model."""
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.NORMAL):
        '''Initialize parser with empty diagram and no namespace.'''
        self.diagram = Diagram()
        self.ns = None # no namespace in draw.io XML
        self.validator = ValidationCollector(validation_level)
        
    def parse_file(self, filepath: Path) -> tuple[Diagram, ValidationCollector]:
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
            report_path = Path(filepath).parent / 'validation_reports'
            report_path.mkdir(exist_ok=True)

            # Parse the diagram
            diagram = self.parse_xml(root)
            # Save the report after parsing is complete
            self.validator.save_report(report_path / 'parsing_validation.log')

            return diagram, self.validator
        
        except ET.ParseError as e:
            self.validator.add_result(
                severity=ValidationSeverity.CRITICAL,
                message=f"Failed to parse XML file: {e}",
                element_type="XML"
            )
            # Save report before raising
            self.validator.save_report(report_path / 'parsing_validation.log')
            raise
        except Exception as e:
            self.validator.add_result(
                severity=ValidationSeverity.CRITICAL,
                message=f"Unexpected error during parsing: {str(e)}",
                element_type="Parsing"
            )
            # Save report before raising
            self.validator.save_report(report_path / 'parsing_validation.log')
            raise

    def parse_xml(self, root: ET.Element) -> Diagram:
        """Parse XML content into diagram model"""
        # Get all mxCell elements
        #cells = root.xpath('.//mxCell')
        
        # First pass: Create all groups
        self._parse_groups(root)
        
        # Second pass: Create list nodes (multiple choice questions)
        self._parse_list_nodes(root)
        
        # Third pass: Create regular nodes (including rhombus)
        self._parse_nodes(root)
        
        # Fourth pass: Create edges
        self._parse_edges(root)
        
        return self.diagram

    def _parse_groups(self, root: ET.Element):
        """First pass: Parse group elements"""
        for cell in root.iter('mxCell'):
            if self._is_group(cell):
                group = self._create_group(cell)
                self.diagram.groups[group.id] = group
                
    def _parse_list_nodes(self, root: ET.Element):
        """Second pass: Parse list nodes (multiple choice)"""
        for cell in root.iter('mxCell'):
            if self._is_list_node(cell):
                node = self._create_list_node(cell)
                self.diagram.nodes[node.id] = node
                
                # Add to parent group if applicable 
                parent_id = cell.get('parent')
                if parent_id in self.diagram.groups:
                    self.diagram.groups[parent_id].contained_elements.add(node.id)

    def _parse_nodes(self, root: ET.Element):
        """Third pass: Parse regular nodes (including rhombus)"""
        for cell in root.iter('mxCell'):
            if self._is_node(cell):
                # Skip if already processed as list node
                base_attrs = self._extract_base_attributes(cell)
                if base_attrs['id'] in self.diagram.nodes:
                    continue

                # Check if this is a select option for a list node
                parent_id = cell.get('parent')
                # If parent is UserObject/object, get its parent (the actual list node)
                parent_elem = cell.getparent()
                if parent_elem is not None and parent_elem.tag in ('UserObject', 'object'):
                    parent_id = parent_elem.get('parent')
                # If parent is a list node, add this as an option, but don't create a new node
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
        for cell in root.iter('mxCell'):
            if self._is_edge(cell):
                edge = self._create_edge(cell)
                if edge: # Only add if created successfully
                    self.diagram.edges[edge.id] = edge

    def _is_group(self, cell: ET.Element) -> bool:
        """Check if cell represents a group"""
        if cell.get('vertex') != '1':
            return False
        style = self._parse_style_string(cell.get('style', ''))
        return 'swimlane' in style and 'childLayout' not in style

    def _is_list_node(self, cell: ET.Element) -> bool:
        """Check if cell represents a list node"""
        if cell.get('vertex') != '1':
            return False
        style = self._parse_style_string(cell.get('style', ''))
        return 'swimlane' in style and style.get('childLayout') == 'stackLayout'

    def _is_node(self, cell: ET.Element) -> bool:
        """Check if cell represents a regular node"""
        return (
            cell.get('vertex') == '1' 
            and not self._is_group(cell)
            and not self._is_list_node(cell)
        )

    def _is_edge(self, cell: ET.Element) -> bool:
        """Check if cell represents an edge"""
        return cell.get('edge') == '1'

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
        if wrapper.tag in ('UserObject', 'object'):
            return {
                'id': wrapper.get('id'),
                'label': wrapper.get('label', ''),
                'page_id': self._get_page_id(cell)
            }
        else: 
            return {
                'id': cell.get('id'),
                'label': cell.get('value', ''),
                'page_id': self._get_page_id(cell)
            }

    def _create_group(self, cell: ET.Element) -> Group:
        """Create a Group from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        metadata = self._extract_metadata(cell)
        return Group(
            id=base_attrs['id'],
            label=base_attrs['label'],
            page_id=base_attrs['page_id'],
            metadata=metadata,
            geometry=self._create_geometry(cell),
            contained_elements=set() # Will be populated when processing nodes
        )

    def _create_list_node(self, cell: ET.Element) -> Node:
        """Create a List node from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        metadata = self._extract_metadata(cell)
        return Node(
            id=base_attrs['id'],
            label=base_attrs['label'],
            page_id=base_attrs['page_id'],
            metadata=metadata,
            shape=ShapeType.LIST,
            geometry=self._create_geometry(cell),
            style=self._create_style(cell),
            options=[]  # Will be populated when processing child nodes
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
        
        return Node(
            id=base_attrs['id'],
            label=base_attrs['label'],
            page_id=base_attrs['page_id'],
            metadata=metadata,
            shape=shape,
            geometry=self._create_geometry(cell),
            style=self._create_style(cell)
        )

    def _create_edge(self, cell: ET.Element) -> Optional[Edge]:
        """Create an Edge from cell element"""
        base_attrs = self._extract_base_attributes(cell)
        metadata = self._extract_metadata(cell)

        try:
            return Edge(
                id=base_attrs['id'],
                label=base_attrs['label'],
                page_id=base_attrs['page_id'],
                metadata=metadata,
                source=cell.get('source'),
                target=cell.get('target'),
                # need this for managing flexible validations
                validation_collector = self.validator
                )
        # only needed if one wants to overwrite pydantic's default validation error messages
        # if you decide to use this, remember to refactor: invalid edges that have at least source or 
        # target should be added to the diagram's edges list
        #except ValidationError as ve:
        #    # Format a clearer error message from Pydantic's validation error for every raised error
        #    for error_details in ve.errors():
        #        message = EdgeValidationMessage.format_pydantic_error(error_details, cell)
        #        field_name = '.'.join(str(loc) for loc in error_details['loc'])
        #
        #        self.validator.add_result(
        #            severity = ValidationSeverity.ERROR,
        #            message = message,
        #            element_id = cell.get('ID'),
        #            element_type = 'Edge',
        #            field_name=field_name
        #        )
        #    return None
        # EdgeValidationError is not used right now because validators use pydantic's generic ValueError
        except EdgeValidationError as e:
            self.validator.add_result(
                severity = ValidationSeverity.ERROR,
                message = str(e),
                element_id = e.element_id,
                element_type = 'Edge'
            )
            return None


    def _determine_shape(self, cell: ET.Element) -> ShapeType:
        """Determine shape type from cell style"""
        style = self._parse_style_string(cell.get('style', ''))

        for shape_type in ShapeType:
            # Skip list and rectangle as they are not stored as at all in the style dict
            if shape_type in (ShapeType.LIST, ShapeType.RECTANGLE):
                continue

            # 'ellipse' and 'rhombus' are stored as a key in the style dict
            if shape_type in style.keys():
                return shape_type
            elif style.get('shape') == shape_type:
                return shape_type
        # If not specific shape is found, it's rectangle
        return ShapeType.RECTANGLE

    def _add_option_to_list(self, list_node: Node, option_cell: ET.Element):
        """Add an option to a list node"""
        if not list_node.options:
            list_node.options = []
        list_node.options.append(option_cell.get('value', ''))

    def _extract_metadata(self, cell: ET.Element) -> Optional[ElementMetadata]:
        """Extract metadata from cell or its parent UserObject"""
        # Check for parent UserObject/object
        parent = cell.getparent()
        if parent is not None and parent.tag in ('UserObject', 'object'):
            return ElementMetadata(
                name=parent.get('name'),
                # Add other metadata extraction as needed
            )
        return None

    def _extract_numeric_constraints(self, cell: ET.Element) -> Optional[NumericConstraints]:
        """Extract numeric constraints for hexagon/ellipse nodes"""
        parent = cell.getparent()
        if parent is not None and parent.tag in ('UserObject', 'object'):
            return NumericConstraints(
                min_value=float(parent.get('min_value')) if parent.get('min_value') else None,
                max_value=float(parent.get('max_value')) if parent.get('max_value') else None,
                constraint_message=parent.get('constraint_message')
            )
        return None

    def _create_geometry(self, cell: ET.Element) -> Geometry:
        """Create Geometry from cell"""
        geometry = cell.find('mxGeometry')
        if geometry is not None:
            return Geometry(
                x=float(geometry.get('x', 0)),
                y=float(geometry.get('y', 0)),
                width=float(geometry.get('width', 0)),
                height=float(geometry.get('height', 0))
            )
        return Geometry()

    def _create_style(self, cell: ET.Element) -> Style:
        """Create Style from cell"""
        style_dict = self._parse_style_string(cell.get('style', ''))
        return Style(
            fill_color=style_dict.get('fillColor'),
            stroke_color=style_dict.get('strokeColor'),
            rounded=style_dict.get('rounded', '0') == '1',
            dashed=style_dict.get('dashed', '0') == '1'
        )

    def _parse_style_string(self, style_str: str) -> Dict[str, str]:
        """Parse draw.io style string into dictionary"""
        style_dict = {}
        if style_str:
            for item in style_str.split(';'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    style_dict[key.strip()] = value.strip()
                else:
                    style_dict[item] = ''

        return style_dict

    def _get_page_id(self, cell: ET.Element) -> str:
        """Get page ID for element"""
        # Walk up the tree to find the parent page
        current = cell
        while current is not None:
            if current.tag == 'diagram':
                return current.get('id', '')
            current = current.getparent()
        return ''