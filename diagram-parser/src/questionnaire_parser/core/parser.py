"""
Parser for converting draw.io XML files into our diagram model.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Set
from logging import getLogger
from pydantic import ValidationError

from questionnaire_parser.models.diagram import (
    Diagram, Node, Edge, Container, Geometry, Style, 
    ShapeType, BaseElement
)
from questionnaire_parser.exceptions import XMLParsingError, ValidationError


logger = getLogger(__name__)

class DrawIoParser:
    """Parses draw.io XML files into our diagram model"""
    
    def __init__(self):
        self.namespace = None # no namespace in draw.io XML
        # Map draw.io shape styles to our ShapeType enum
        self.shape_map = {
            'rhombus': ShapeType.RHOMBUS,
            'hexagon': ShapeType.HEXAGON,
            'ellipse': ShapeType.ELLIPSE,
            'rectangle': ShapeType.RECTANGLE,
            'callout': ShapeType.CALLOUT
        }

    def parse_file(self, filepath: str) -> Diagram:
        """Parse a draw.io XML file into our diagram model"""
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            return self.parse_xml(root)
        except ET.ParseError as e:
            raise XMLParsingError(f"Failed to parse XML file: {e}")
        except Exception as e:
            raise XMLParsingError(f"Unexpected error during parsing: {e}")

    def parse_xml(self, root: ET.Element) -> Diagram:
        """Convert XML root element into our diagram representation"""
        # Initialize collections for diagram elements
        nodes: Dict[str, Node] = {}
        edges: Dict[str, Edge] = {}
        containers: Dict[str, Container] = {}
        
        # First pass: Create all nodes and containers
        for cell in root.findall('.//mxCell', self.namespace):
            element_data = self._parse_element(cell)
            if not element_data:
                continue
                
            if self._is_node(cell):
                node = self._create_node(element_data)
                nodes[node.id] = node
            elif self._is_container(cell):
                container = self._create_container(element_data)
                containers[container.id] = container
                
        # Second pass: Create edges
        for cell in root.findall('.//mxCell', self.namespace):
            if self._is_edge(cell):
                edge = self._create_edge(cell)
                if edge:
                    edges[edge.id] = edge
                    
        # Build and validate the diagram
        try:
            diagram = Diagram(
                nodes=nodes,
                edges=edges,
                containers=containers
            )
            return diagram
        except ValidationError as e:
            logger.error(f"Failed to create valid diagram: {e}")
            raise

    def _parse_element(self, element: ET.Element) -> Optional[Dict]:
        """Extract basic properties from an mxCell element"""
        element_id = element.get('id')
        if not element_id or element_id in ('0', '1'):  # Skip root elements
            return None
            
        return {
            'id': element_id,
            'style': self._parse_style(element.get('style', '')),
            'geometry': self._parse_geometry(element.find('mxGeometry', self.namespace)),
            'label': element.get('value', ''),
            'parent': element.get('parent'),
            'source': element.get('source'),
            'target': element.get('target')
        }

    def _parse_style(self, style_str: str) -> Style:
        """Convert draw.io style string into a Style model"""
        if not style_str:
            return Style()
            
        # Parse style string into dictionary
        style_dict = {}
        for item in style_str.split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                style_dict[key.strip()] = value.strip()
        
        # Map to our Style model
        shape = self._determine_shape(style_dict)
        rounded = style_dict.get('rounded', '0') == '1'
        dashed = style_dict.get('dashed', '0') == '1'
        fill_color = style_dict.get('fillColor')
        stroke_color = style_dict.get('strokeColor')
        
        return Style(
            shape=shape,
            rounded=rounded,
            dashed=dashed,
            fill_color=fill_color,
            stroke_color=stroke_color
        )

    def _determine_shape(self, style_dict: Dict[str, str]) -> Optional[ShapeType]:
        """Determine the shape type from style properties"""
        shape = style_dict.get('shape', '')
        return self.shape_map.get(shape, ShapeType.RECTANGLE)

    def _parse_geometry(self, geometry: Optional[ET.Element]) -> Optional[Geometry]:
        """Extract geometric properties from mxGeometry element"""
        if geometry is None:
            return None
            
        try:
            return Geometry(
                x=float(geometry.get('x', 0)),
                y=float(geometry.get('y', 0)),
                width=float(geometry.get('width', 0)),
                height=float(geometry.get('height', 0))
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid geometry values: {e}")
            return None

    def _is_node(self, element: ET.Element) -> bool:
        """Determine if an element represents a node"""
        style = element.get('style', '')
        return (
            not element.get('edge') == '1' 
            and 'container=1' not in style
        )

    def _is_edge(self, element: ET.Element) -> bool:
        """Determine if an element represents an edge"""
        return element.get('edge') == '1'

    def _is_container(self, element: ET.Element) -> bool:
        """Determine if an element represents a container"""
        style = element.get('style', '')
        return 'container=1' in style

    def _create_node(self, data: Dict) -> Node:
        """Create a node from parsed element data"""
        return Node(
            id=data['id'],
            geometry=data['geometry'],
            style=data['style'],
            label=data['label']
        )

    def _create_edge(self, element: ET.Element) -> Optional[Edge]:
        """Create an edge from an mxCell element"""
        data = self._parse_element(element)
        if not data or not data['source'] or not data['target']:
            return None
            
        return Edge(
            id=data['id'],
            style=data['style'],
            label=data['label'],
            source=data['source'],
            target=data['target']
        )

    def _create_container(self, data: Dict) -> Container:
        """Create a container from parsed element data"""
        return Container(
            id=data['id'],
            geometry=data['geometry'],
            style=data['style'],
            label=data['label'],
            contained_elements=[]
        )

    def validate_diagram(self, diagram: Diagram):
        """Perform additional validation on the parsed diagram"""
        # Verify it's a DAG
        if not diagram.validate_dag():
            raise ValidationError("Diagram contains cycles")
            
        # Verify single entry point
        entry_points = diagram.get_entry_points()
        if not entry_points:
            raise ValidationError("Diagram has no entry points")
        if len(entry_points) > 1:
            logger.warning(f"Diagram has multiple entry points: {entry_points}")