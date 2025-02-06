from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, validator
from questionnaire_parser.models.diagram import Diagram, NodeType, DiagramNode, DiagramEdge

class EdgeValidationError(Exception):
    """Raised when edge validation fails"""
    pass

class EdgeLogic(BaseModel):
    """Represents the logical condition on an edge"""
    type: str  # 'condition' or 'operator'
    operator: Optional[str] = None  # '=', '>', '<', '>=', '<=', 'contains'
    node: Optional[str] = None
    value: Optional[str] = None
    conditions: Optional[List['EdgeLogic']] = None

class EdgeRules(BaseModel):
    """Validates edge rules and calculates edge logic"""
    diagram: Diagram

    @validator('diagram')
    @classmethod
    def validate_edge_connections(cls, v: Diagram) -> Diagram:
        """Validate that edges connect to valid nodes"""
        for edge_id, edge in v.edges.items():
            if edge.source not in v.nodes:
                raise EdgeValidationError(
                    f"Edge {edge_id} source {edge.source} does not exist")
            if edge.target not in v.nodes:
                raise EdgeValidationError(
                    f"Edge {edge_id} target {edge.target} does not exist")
        return v

    @validator('diagram')
    @classmethod
    def validate_select_edges(cls, v: Diagram) -> Diagram:
        """Validate edges for select nodes"""
        for node_id, node in v.nodes.items():
            if node.node_type in [NodeType.SELECT_ONE, NodeType.SELECT_MULTIPLE]:
                # Select nodes shouldn't have direct outgoing edges
                outgoing = [e for e in v.edges.values() if e.source == node_id]
                if outgoing:
                    raise EdgeValidationError(
                        f"Select node {node_id} has direct outgoing edges")
        return v

    @validator('diagram')
    @classmethod
    def validate_rhombus_edges(cls, v: Diagram) -> Diagram:
        """Validate edges for rhombus nodes"""
        for node_id, node in v.nodes.items():
            if node.node_type == NodeType.RHOMBUS:
                outgoing = [e for e in v.edges.values() if e.source == node_id]
                if len(outgoing) != 2:
                    raise EdgeValidationError(
                        f"Rhombus node {node_id} must have exactly two outgoing edges")
                
                # Check for Yes/No labels
                labels = [e.label for e in outgoing]
                if 'Yes' not in labels or 'No' not in labels:
                    raise EdgeValidationError(
                        f"Rhombus node {node_id} edges must be labeled 'Yes' and 'No'")
        return v

    def calculate_edge_logic(self) -> Dict[str, EdgeLogic]:
        """Calculate the logic for each edge in the diagram"""
        edge_logic = {}
        
        for edge_id, edge in self.diagram.edges.items():
            source_node = self.diagram.nodes[edge.source]
            logic = self._calculate_node_edge_logic(source_node, edge)
            if logic:
                edge_logic[edge_id] = logic
                
        return edge_logic

    def _calculate_node_edge_logic(self, 
                                 node: DiagramNode, 
                                 edge: DiagramEdge) -> Optional[EdgeLogic]:
        """Calculate edge logic based on source node type"""
        if node.node_type == NodeType.SELECT_ONE:
            return EdgeLogic(
                type='condition',
                operator='=',
                node=node.id,
                value=edge.label
            )
            
        elif node.node_type == NodeType.SELECT_MULTIPLE:
            return EdgeLogic(
                type='condition',
                operator='contains',
                node=node.id,
                value=edge.label
            )
            
        elif node.node_type == NodeType.RHOMBUS:
            referenced_node = self.diagram.nodes[node.attributes['reference_node']]
            return self._calculate_rhombus_logic(node, edge, referenced_node)
            
        return None

    def _calculate_rhombus_logic(self, 
                                rhombus: DiagramNode, 
                                edge: DiagramEdge,
                                referenced_node: DiagramNode) -> EdgeLogic:
        """Calculate logic for rhombus node edges"""
        if referenced_node.node_type in [NodeType.INTEGER, NodeType.DECIMAL]:
            # Parse equation from rhombus label
            operator, value = self._parse_numeric_condition(rhombus.label)
            return EdgeLogic(
                type='condition',
                operator=operator,
                node=referenced_node.id,
                value=value
            )
            
        elif referenced_node.node_type == NodeType.SELECT_MULTIPLE:
            # Extract option from square brackets
            option = self._extract_option_from_label(rhombus.label)
            return EdgeLogic(
                type='condition',
                operator='contains',
                node=referenced_node.id,
                value=option
            )
            
        else:  # SELECT_ONE or FLAG
            return EdgeLogic(
                type='condition',
                operator='=',
                node=referenced_node.id,
                value=edge.label == 'Yes'
            )

    @staticmethod
    def _parse_numeric_condition(label: str) -> Tuple[str, str]:
        """Parse numeric condition from rhombus label"""
        # Implementation for parsing equations like "Age > 5"
        pass

    @staticmethod
    def _extract_option_from_label(label: str) -> str:
        """Extract option from square brackets in label"""
        # Implementation for extracting [Option] from label
        pass
