from typing import List
from pydantic import BaseModel, validator
from questionnaire_parser.models.diagram import Diagram, NodeType, DiagramNode

class NodeValidationError(Exception):
    pass

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
