from typing import Dict, List, Optional, Set, Tuple
from lxml import etree as ET
from logging import getLogger
from pydantic import ValidationError

from questionnaire_parser.models.diagram import (
    Diagram, Node, Edge, Group, Geometry, Style, ShapeType,
    NodeMetadata, NumericConstraints
)
from questionnaire_parser.exceptions.parsing import XMLParsingError, NodeValidationError

logger = getLogger(__name__)

class DrawIoParser:
    """Parser for converting draw.io XML files into our diagram model."""
    
    def __init__(self):
        self.ns = None # no namespace in draw.io XML
        
    def parse_file(self, filepath: str) -> Diagram:
        """Parse a draw.io XML file into our diagram model."""
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            return self.parse_xml(root)
        except ET.ParseError as e:
            raise XMLParsingError(f"Failed to parse XML file: {e}")
        except Exception as e:
            raise XMLParsingError(f"Unexpected error during parsing: {e}")

    def parse_xml(self, root: ET.Element) -> Diagram:
        """Convert XML root element into our diagram model."""
        # Initialize empty diagram
        diagram = Diagram()

        # Elements with user defined tags are mxCell nodes wrapped in UserObject/object elements
        # Dictionary to store parent relationships {mxCell ID: parent element object}
        parent_map: Dict[str, ET.Element] = {}

        # Track processed mxCell IDs to avoid counting children of parent-wrapped mxCells twice
        processed_ids: set[str] = set()
        
        # Find all diagram elements (direct mxCells and parent-wrapped mxCells)
        element_nodes: Set[ET.Element] = set()
        
       # Process UserObject/object elements first (they take precedence)
       # Find all UserObject/object elements that contain mxCells
       # Store references of mxCells to parent elements in parent_map
       # Track processed mxCells in processed_ids
        for parent_type in ['UserObject', 'object']:
            for parent in root.findall(f'.//{parent_type}', self.ns):
                mxCell = parent.find('mxCell', self.ns)
                if mxCell is not None:
                    cell_id = parent.get('id') # if UserObject/object, ID is stored in parent element, not mxCell nodes 
                    if cell_id:
                        parent_map[cell_id] = parent
                        element_nodes.add(mxCell)
                        processed_ids.add(cell_id)

        # Then get only direct mxCell elements that haven´t been processed
        # as children of UserObject/object elements
        for mxCell in root.findall('.//mxCell', self.ns):
            cell_id = mxCell.get('id')
            if cell_id and cell_id not in processed_ids:
                element_nodes.add(mxCell)
                processed_ids.add(cell_id)

        # First pass: Create all basic nodes and groups
        for cell in element_nodes:
            cell_data = self._parse_cell(cell)
            if not cell_data:
                continue
            
            if self._is_node(cell):
                try:
                    node = self._create_node(cell_data)
                    diagram.nodes[node.id] = node
                except ValidationError as e:
                    logger.warning(f"Failed to create node from cell {cell_data.get('id')}: {e}")
                    
            elif self._is_group(cell):
                try:
                    group = self._create_group(cell_data)
                    diagram.groups[group.id] = group
                except ValidationError as e:
                    logger.warning(f"Failed to create group from cell {cell_data.get('id')}: {e}")

        # Second pass: Create edges and establish relationships
        for cell in root.findall('.//mxCell', self.ns):
            if self._is_edge(cell):
                try:
                    edge = self._create_edge(cell)
                    if edge:
                        diagram.edges[edge.id] = edge
                except ValidationError as e:
                    logger.warning(f"Failed to create edge from cell {cell.get('id')}: {e}")

        # Third pass: Resolve group memberships
        self._resolve_group_memberships(diagram)
        
        # Final validation
        if not diagram.validate_dag():
            raise NodeValidationError("Resulting graph is not a valid DAG")
            
        return diagram

    def _parse_cell(self, cell: ET.Element) -> Optional[Dict]:
        """Extract basic properties from an mxCell element."""
        cell_id = cell.get('id')
        # For cells with UserObject/object parents, get ID and label from parent,
        # the parent is then the 'grandparent' of the cell
        if not cell_id:
            wrapper = cell.getparent()
            cell_id = wrapper.get('id')
            label = wrapper.get('label', '')
            # get the parent of the wrappper
            parent = wrapper.getparent()
        else:
            label = cell.get('value', '')
            parent = cell.getparent()
    
        if not cell_id or cell_id in ('0', '1'):  # Skip root elements
            return None
            
        style = cell.get('style', '')
        geometry = cell.find('mxGeometry', self.ns)
        
        return {
            'id': cell_id,
            'style': self._parse_style(style),
            'geometry': self._parse_geometry(geometry),
            'label': label,
            'parent': parent, 
            'source': cell.get('source'),
            'target': cell.get('target'),
            'page_id': self._get_page_id(cell)
        }

    def _parse_style(self, style_str: str) -> Style:
        """Convert draw.io style string into our Style model."""
        style_dict = {}
        for item in style_str.split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                style_dict[key.strip()] = value.strip()
                
        return Style(
            fill_color=style_dict.get('fillColor'),
            stroke_color=style_dict.get('strokeColor'),
            rounded='rounded=1' in style_str,
            dashed='dashed=1' in style_str
        )

    def _parse_geometry(self, geometry: Optional[ET.Element]) -> Geometry:
        """Extract geometric properties from mxGeometry element."""
        if geometry is None:
            return Geometry()
            
        return Geometry(
            x=float(geometry.get('x', 0)),
            y=float(geometry.get('y', 0)),
            width=float(geometry.get('width', 0)),
            height=float(geometry.get('height', 0))
        )

    def _determine_shape_type(self, style_dict: Dict[str, str]) -> ShapeType:
       """Determine the shape type based on style properties.
    
       Draw.io has two different ways of encoding shapes in the style string:
       1. Some shapes (like rhombus, ellipse) appear directly as keys in the style string
          Example: "rhombus;whiteSpace=wrap;html=1;"
          These become direct keys in the style_dict
    
       2. Other shapes (like hexagon, callout) use a shape=... format
          Example: "shape=hexagon;whiteSpace=wrap;html=1;"
          These are accessed via style_dict.get('shape')
    
       The reason for this inconsistency is not documented but appears to be 
       historical in the draw.io codebase.
       """
       # Check if it's a list (swimlane with stackLayout)
       if 'swimlane' in style_dict and style_dict.get('childLayout') == 'stackLayout':
           return ShapeType.LIST
    
       # Case 1: Shapes that appear directly in style string
       if 'rhombus' in style_dict:
           return ShapeType.RHOMBUS
       if 'ellipse' in style_dict:
           return ShapeType.ELLIPSE
           
       # Case 2: Shapes that use shape=... format
       shape = style_dict.get('shape', '')
       shape_mapping = {
           'hexagon': ShapeType.HEXAGON,
           'callout': ShapeType.CALLOUT,
           'offPageConnector': ShapeType.OFFPAGE
       }
    
       return shape_mapping.get(shape, ShapeType.RECTANGLE)  # Default to rectangle if no specific shape

    def _parse_numeric_constraints(self, cell: ET.Element) -> Optional[NumericConstraints]:
        """Extract numeric constraints for hexagon/ellipse nodes."""
        constraints = {}
        
        # Look for constraint attributes in the cell
        min_value = cell.get('min')
        max_value = cell.get('max')
        message = cell.get('constraint_message')
        
        if any([min_value, max_value, message]):
            try:
                constraints['min_value'] = float(min_value) if min_value else None
                constraints['max_value'] = float(max_value) if max_value else None
                constraints['constraint_message'] = message
                return NumericConstraints(**constraints)
            except ValueError:
                logger.warning(f"Invalid numeric constraints in cell {cell.get('id')}")
                
        return None

    def _is_node(self, cell: ET.Element) -> bool:
        """Determine if a cell represents a node."""
        return (
            cell.get('vertex') == '1' and
            not self._is_group(cell)
        )

    def _is_edge(self, cell: ET.Element) -> bool:
        """Determine if a cell represents an edge."""
        return cell.get('edge') == '1'

    def _is_group(self, cell: ET.Element) -> bool:
        """Determine if a cell represents a group."""
        style = cell.get('style', '')
        return (
            'swimlane' in style and
            'childLayout' not in style
        )

    def _get_page_id(self, cell: ET.Element) -> str:
        """Get the ID of the diagram (page) containing this cell.
        
        The draw.io XML structure has diagram elements that represent pages,
        each with a unique ID. This method traverses up the XML tree to find
        the parent diagram element and returns its ID.
        """
        # Traverse up the tree to find the diagram element
        parent = cell
        while parent is not None:
            if parent.tag == 'diagram':
                return parent.get('id', '')
            parent = parent.getparent()
        return ''

    def _create_node(self, data: Dict) -> Node:
        """Create a node from parsed cell data."""
        shape_type = self._determine_shape_type(data['style'])
        
        # Extract options for list nodes
        options = None
        if shape_type == ShapeType.LIST:
            options = self._extract_list_options(data)
            
        metadata = NodeMetadata(
            name=data.get('name'),
            numeric_constraints=self._parse_numeric_constraints(data)
        )
        
        return Node(
            id=data['id'],
            shape=shape_type,
            label=data['label'],
            geometry=data['geometry'],
            style=data['style'],
            options=options,
            metadata=metadata,
            page_id=data['page_id']
        )

    def _create_edge(self, cell: ET.Element) -> Optional[Edge]:
        """Create an edge from a cell element."""
        source = cell.get('source')
        target = cell.get('target')
        
        if not source or not target:
            return None
            
        return Edge(
            id=cell.get('id'),
            source=source,
            target=target,
            label=cell.get('value', ''),
            page_id=self._get_page_id(cell)
        )

    def _create_group(self, data: Dict) -> Group:
        """Create a group from parsed cell data."""
        return Group(
            id=data['id'],
            label=data['label'],
            geometry=data['geometry'],
            contained_elements=set(),
            page_id=data['page_id']
        )

    def _extract_list_options(self, data: Dict) -> List[str]:
        """Extract options from a list node."""
        # This would need to find and parse child elements
        # For now, returning empty list as placeholder
        return []

    def _resolve_group_memberships(self, diagram: Diagram):
        """Establish parent-child relationships between groups and nodes."""
        # Create a mapping of parent IDs to their children
        parent_map: Dict[str, Set[str]] = {}
        
        # First pass: collect all parent-child relationships
        for node_id, node in diagram.nodes.items():
            parent = node.parent_id
            if parent in diagram.groups:
                if parent not in parent_map:
                    parent_map[parent] = set()
                parent_map[parent].add(node_id)
        
        # Second pass: update group contained_elements
        for group_id, children in parent_map.items():
            diagram.groups[group_id].contained_elements = children