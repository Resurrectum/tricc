import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
from pydantic import ValidationError
from questionnaire_parser.models.diagram import (Diagram, DiagramNode, DiagramEdge, DiagramContainer, NodeType, GeometryModel, Severity, SelectOption)
from questionnaire_parser.exceptions.parsing import XMLParsingError

class DrawIoParser:
    """Handles parsing of draw.io XML files into Pydantic models"""
    
    def __init__(self):
        #self.ns = {'': 'http://www.w3.org/2000/svg'}
        self.ns = None # no namespace
    
    def parse_file(self, filepath: str) -> Diagram:
        """Parse a draw.io XML file into our Pydantic models"""
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            return self.parse_xml(root)
        except ET.ParseError as e:
            raise XMLParsingError(f"Failed to parse XML file: {e}")
        except ValidationError as e:
            raise XMLParsingError(f"Validation error in parsed data: {e}")
        except Exception as e:
            raise XMLParsingError(f"Unexpected error during parsing: {e}")

    def parse_xml(self, root: ET.Element) -> Diagram:
        """Convert XML root element into Pydantic diagram representation"""
        diagram_data: Dict[str, Dict] = {
            "nodes": {},
            "edges": {},
            "containers": {},
            "select_options": {}
        }

        # Keep track of processed mxCells
        processed_cell_ids = set()

        # First pass: Process UserObjects
        user_objects = root.findall('.//UserObject', self.ns)
        for user_object in user_objects:
            cell = user_object.find('mxCell')
            if cell is not None:
                processed_cell_ids.add(cell.get('id'))
                element_data = self._parse_element(user_object, cell)
                if element_data:
                    if self._is_node(user_object):
                        node = self._create_node(element_data)
                        if node:
                            diagram_data["nodes"][node.id] = node
                    elif self._is_container(user_object):
                        container = self._create_container(element_data)
                        if container:
                            diagram_data["containers"][container.id] = container

        # Process remaining mxCells
        mx_cells = root.findall('.//mxCell', self.ns)
        for cell in mx_cells:
            cell_id = cell.get('id')
            if cell_id not in processed_cell_ids:
                element_data = self._parse_element(cell)
                if element_data:
                    if self._is_edge(cell):
                        edge = self._create_edge(cell)
                        if edge:
                            diagram_data["edges"][edge.id] = edge
                    elif self._is_node(cell):
                        node = self._create_node(element_data)
                        if node:
                            diagram_data["nodes"][node.id] = node
                    elif self._is_container(cell):
                        container = self._create_container(element_data)
                        if container:
                            diagram_data["containers"][container.id] = container

        # Second pass: Process edges from UserObjects
        for user_object in user_objects:
            cell = user_object.find('mxCell')
            if cell is not None and self._is_edge(cell):
                edge = self._create_edge(cell)
                if edge:
                    diagram_data["edges"][edge.id] = edge

        return Diagram(**diagram_data)

    def _parse_element(self, element: ET.Element) -> Optional[Dict]:
        """Extract basic properties from an mxCell or UserObject element"""
        element_id = element.get('id')
        if not element_id or element_id in ('0', '1'):
            return None
            
        return {
            'id': element_id,
            'style': self._parse_style(element.get('style', '')),
            'geometry': self._parse_geometry(element.find('mxGeometry', self.ns)),
            'value': element.get('value', ''),
            'parent': element.get('parent'),
            'source': element.get('source'),
            'target': element.get('target')
        }


    def _parse_style(self, style_str: str) -> Dict[str, str]:
           """Convert draw.io style string into a dictionary"""
           if not style_str:
               return {}
               
           style_dict = {}
           for item in style_str.split(';'):
               if '=' in item:
                   key, value = item.split('=', 1)
                   style_dict[key.strip()] = value.strip()
           return style_dict

    def _parse_geometry(self, geometry: Optional[ET.Element]) -> Dict[str, float]:
        """Extract geometric properties from mxGeometry element"""
        if geometry is None:
            return {}
            
        return {
            'x': float(geometry.get('x', 0)),
            'y': float(geometry.get('y', 0)),
            'width': float(geometry.get('width', 0)),
            'height': float(geometry.get('height', 0))
        }



    def _is_node(self, element: ET.Element) -> bool:
        """Determine if an element represents a node"""
        style = self._parse_style(element.get('style', ''))
        return not (element.get('edge') == '1' or 
                   style.get('container') == '1')

    def _is_edge(self, element: ET.Element) -> bool:
        """Determine if an element represents an edge"""
        return element.get('edge') == '1'

    def _is_container(self, element: ET.Element) -> bool:
        """Determine if an element represents a container"""
        style = self._parse_style(element.get('style', ''))
        return style.get('container') == '1'

    def _create_container(self, data: Dict) -> Optional[DiagramContainer]:
        """Create a container from parsed element data"""
        try:
            return DiagramContainer(
                id=data['id'],
                element_type='container',
                visual_properties=data['style'],
                heading=data['value'],
                contained_elements=[],
                container_type='page'  # Default type, should be determined from style
            )
        except ValidationError:
            return None

    def _determine_node_type(self, style_dict: Dict[str, str], 
                           element_data: Dict) -> NodeType:
        """Determine node type based on shape and style"""
        shape = style_dict.get('shape', '')
        
        if shape == 'callout':
            return NodeType.TEXT
        elif shape == 'offPageConnector':
            return NodeType.GOTO
        elif shape == 'rhombus':
            return NodeType.RHOMBUS
        elif shape == 'hexagon':
            return NodeType.INTEGER
        elif shape == 'ellipse':
            return NodeType.DECIMAL
            
        # Handle other cases based on style and context
        return NodeType.NOTE  # Default type

    def _create_node(self, data: Dict) -> Optional[DiagramNode]:
        """Create a node from parsed element data"""
        try:
            node_type = self._determine_node_type(data['style'], data)
            geometry = GeometryModel(**data['geometry'])
            
            return DiagramNode(
                id=data['id'],
                element_type='node',
                node_type=node_type,
                visual_properties=data['style'],
                geometry=geometry,
                label=data['value'],
                parent_id=data['parent']
            )
        except ValidationError:
            return None

    def _create_edge(self, element: ET.Element) -> Optional[DiagramEdge]:
        """Create an edge from an mxCell"""
        data = self._parse_element(element)
        if not data or not data['source'] or not data['target']:
            return None
            
        try:
            return DiagramEdge(
                id=data['id'],
                element_type='edge',
                visual_properties=data['style'],
                source=data['source'],
                target=data['target'],
                label=data['value']
            )
        except ValidationError:
            return None
    