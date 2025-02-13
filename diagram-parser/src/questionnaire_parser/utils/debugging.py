from typing import Optional, Dict
from lxml import etree as ET
import logging
from questionnaire_parser.models.diagram import Diagram, Node, Edge, Group, ShapeType

logger = logging.getLogger(__name__)

def setup_debug_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def print_xml_structure(element: ET.Element, level: int = 0):
    """Print the XML structure in a readable format"""
    indent = "  " * level
    print(f"{indent}Tag: {element.tag}")

    # Print attributes
    if element.attrib:
        print(f"{indent}Attributes:")
        for key, value in element.attrib.items():
            print(f"{indent}  {key}: {value}")

    # Print text content if any
    if element.text and element.text.strip():
        print(f"{indent}Text: {element.text.strip()}")

    # Recursively print children
    for child in element:
        print_xml_structure(child, level + 1)

def inspect_diagram(diagram: Diagram):
    """Print a summary of the parsed diagram"""
    print("\n=== Diagram Summary ===")
    print(f"Total nodes: {len(diagram.nodes)}")
    print(f"Total edges: {len(diagram.edges)}")
    print(f"Total groups: {len(diagram.groups)}")

    print("\n=== Amount of Node Types ===")
    node_types : dict[ShapeType, int] = {}
    for node in diagram.nodes.values():
        node_type = node.shape.value
        node_types[node_type] = node_types.get(node_type, 0) + 1
    for node_type, count in node_types.items():
        print(f"{node_type}: {count}")

def inspect_mxcell(cell: ET.Element, parent_map: Optional[Dict[str, ET.Element]] = None):
    """Debug information about an mxCell element"""
    cell_id = cell.get('id')
    print(f"\n=== mxCell {cell_id} ===")
    print("Attributes:", dict(cell.attrib))

    # If this cell has a UserObject/object parent, show its attributes
    if parent_map and cell_id in parent_map:
        parent = parent_map[cell_id]
        print(f"Parent ({parent.tag}) attributes:", dict(parent.attrib))

    # Show geometry if present
    geometry = cell.find('mxGeometry')
    if geometry is not None:
        print("Geometry:", dict(geometry.attrib))

    # Show style parsed
    style = cell.get('style', '')
    if style:
        style_dict = {}
        for item in style.split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                style_dict[key.strip()] = value.strip()
        print("Parsed style:", style_dict)

def examine_node_connections(diagram: Diagram):
    """Analyze node connections and potential issues"""
    print("\n=== Node Connections Analysis ===")

    # Check for nodes with no incoming edges
    entry_points = diagram.get_entry_points()
    print(f"Entry points (nodes with no incoming edges): {entry_points}")

    # Check for nodes with no outgoing edges
    terminal_nodes = []
    for node_id in diagram.nodes:
        has_outgoing = any(edge.source == node_id for edge in diagram.edges.values())
        if not has_outgoing:
            terminal_nodes.append(node_id)
    print(f"Terminal nodes (no outgoing edges): {terminal_nodes}")

    # Check for isolated nodes
    isolated_nodes = []
    for node_id in diagram.nodes:
        has_incoming = any(edge.target == node_id for edge in diagram.edges.values())
        has_outgoing = any(edge.source == node_id for edge in diagram.edges.values())
        if not has_incoming and not has_outgoing:
            isolated_nodes.append(node_id)
    print(f"Isolated nodes (no connections): {isolated_nodes}")

# Example usage
def debug_parsing(xml_path: str):
    """Run a complete debugging session for parsing a draw.io file"""
    setup_debug_logging()

    # Create parser and parse diagram
    from questionnaire_parser.core.parser import DrawIoParser
    parser = DrawIoParser()
    diagram = parser.parse_file(xml_path)

    # Inspect results
    inspect_diagram(diagram)
    examine_node_connections(diagram)