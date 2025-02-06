from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from questionnaire_parser.core.parser import DrawIoParser
from questionnaire_parser.models.diagram import NodeType, Diagram
from questionnaire_parser.exceptions.parsing import XMLParsingError

# Test fixtures provide reusable test data
@pytest.fixture
def simple_node_xml():
    """Provides XML for a simple questionnaire node"""
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <mxGraphModel>
        <root>
            <mxCell id="0"/>
            <mxCell id="1" parent="0"/>
            <mxCell id="2" value="Do you have fever?" style="shape=rectangle" vertex="1">
                <mxGeometry x="100" y="100" width="120" height="60"/>
            </mxCell>
        </root>
    </mxGraphModel>'''

@pytest.fixture
def parser():
    """Provides a fresh parser instance for each test"""
    return DrawIoParser()

def test_parse_simple_node(parser, simple_node_xml):
    """Test parsing of a single node from XML"""
    # Convert string to ElementTree
    root = ET.fromstring(simple_node_xml)
    
    # Parse the XML
    diagram = parser.parse_xml(root)
    
    # Verify we got a valid Diagram object
    assert isinstance(diagram, Diagram)
    
    # Check the node was parsed correctly
    assert len(diagram.nodes) == 1
    node = diagram.nodes["2"]
    assert node.label == "Do you have fever?"
    assert node.geometry.x == 100
    assert node.geometry.y == 100

def test_parse_invalid_xml(parser):
    """Test that invalid XML raises appropriate error"""
    with pytest.raises(XMLParsingError):
        parser.parse_file("nonexistent_file.xml")

def test_node_type_identification(parser):
    """Test correct identification of node types based on shape"""
    xml_string = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxGraphModel>
        <root>
            <mxCell id="1" value="Question" style="shape=rhombus" vertex="1"/>
            <mxCell id="2" value="Number" style="shape=hexagon" vertex="1"/>
        </root>
    </mxGraphModel>'''
    
    root = ET.fromstring(xml_string)
    diagram = parser.parse_xml(root)
    
    assert diagram.nodes["1"].node_type == NodeType.RHOMBUS
    assert diagram.nodes["2"].node_type == NodeType.INTEGER

def test_edge_parsing(parser):
    """Test parsing of edges between nodes"""
    xml_string = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxGraphModel>
        <root>
            <mxCell id="1" value="Question 1" style="shape=rectangle" vertex="1"/>
            <mxCell id="2" value="Question 2" style="shape=rectangle" vertex="1"/>
            <mxCell id="3" edge="1" source="1" target="2" value="Yes"/>
        </root>
    </mxGraphModel>'''
    
    root = ET.fromstring(xml_string)
    diagram = parser.parse_xml(root)
    
    # Verify edge was created correctly
    assert len(diagram.edges) == 1
    edge = diagram.edges["3"]
    assert edge.source == "1"
    assert edge.target == "2"
    assert edge.label == "Yes"

def test_container_parsing(parser):
    """Test parsing of container elements"""
    xml_string = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxGraphModel>
        <root>
            <mxCell id="1" value="Container" style="container=1" vertex="1"/>
            <mxCell id="2" value="Question" parent="1" style="shape=rectangle" vertex="1"/>
        </root>
    </mxGraphModel>'''
    
    root = ET.fromstring(xml_string)
    diagram = parser.parse_xml(root)
    
    # Verify container relationship
    assert "1" in diagram.containers
    container = diagram.containers["1"]
    assert "2" in container.contained_elements
