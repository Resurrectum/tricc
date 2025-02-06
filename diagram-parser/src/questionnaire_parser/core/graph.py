from typing import Dict, Optional, Tuple
import networkx as nx
from pydantic import ValidationError
from questionnaire_parser.models.diagram import (
    Diagram, DiagramNode, DiagramEdge, NodeType, SelectOption
)

class GraphConversionError(Exception):
    """Raised when there are errors converting the diagram to a NetworkX graph"""
    pass

class QuestionnaireGraph:
    """Handles conversion between Pydantic models and NetworkX graphs"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self._entry_point: Optional[str] = None

    def from_diagram(self, diagram: Diagram) -> nx.DiGraph:
        """Convert a Pydantic diagram model to a NetworkX graph"""
        try:
            # Create a new directed graph
            self.graph = nx.DiGraph()
            
            # First pass: Add all nodes
            self._add_nodes(diagram)
            
            # Second pass: Add all edges
            self._add_edges(diagram)
            
            # Find entry point (node with no incoming edges)
            self._identify_entry_point()
            
            # Validate graph structure
            self._validate_graph_structure()
            
            return self.graph
            
        except Exception as e:
            raise GraphConversionError(f"Failed to convert diagram to graph: {str(e)}")

    def _add_nodes(self, diagram: Diagram) -> None:
        """Add all nodes from the diagram to the graph with their attributes"""
        for node_id, node in diagram.nodes.items():
            # Convert node attributes to dictionary format
            attrs = node.dict(exclude={'id', 'element_type'})
            
            # Add select options to node attributes if applicable
            if node.node_type in [NodeType.SELECT_ONE, NodeType.SELECT_MULTIPLE]:
                options = [opt for opt in diagram.select_options.values() 
                          if opt.parent_id == node_id]
                attrs['options'] = [opt.dict() for opt in options]
            
            self.graph.add_node(node_id, **attrs)

    def _add_edges(self, diagram: Diagram) -> None:
        """Add all edges from the diagram to the graph with their attributes"""
        for edge_id, edge in diagram.edges.items():
            # Convert edge attributes to dictionary format
            attrs = edge.dict(exclude={'id', 'element_type', 'source', 'target'})
            
            self.graph.add_edge(edge.source, edge.target, **attrs)

    def _identify_entry_point(self) -> None:
        """Find the entry point of the graph (node with no incoming edges)"""
        entry_points = [node for node in self.graph.nodes 
                       if self.graph.in_degree(node) == 0]
        
        if not entry_points:
            raise GraphConversionError("No entry point found in graph")
        if len(entry_points) > 1:
            raise GraphConversionError("Multiple entry points found in graph")
            
        self._entry_point = entry_points[0]

    def _validate_graph_structure(self) -> None:
        """Validate the basic structure of the graph"""
        # Check if graph is a DAG
        if not nx.is_directed_acyclic_graph(self.graph):
            raise GraphConversionError("Graph contains cycles")
            
        # Check if all nodes are reachable from entry point
        reachable = set(nx.descendants(self.graph, self._entry_point))
        reachable.add(self._entry_point)
        unreachable = set(self.graph.nodes) - reachable
        
        if unreachable:
            raise GraphConversionError(
                f"Nodes not reachable from entry point: {unreachable}")

    def simplify_graph(self) -> None:
        """Apply simplification rules to the graph structure"""
        self._merge_consecutive_notes()
        self._resolve_goto_nodes()
        self._flatten_containers()
        self._consolidate_select_options()

    def _merge_consecutive_notes(self) -> None:
        """Merge consecutive note nodes into single nodes"""
        while True:
            merged = False
            for node in list(self.graph.nodes):
                if self.graph.nodes[node].get('node_type') == NodeType.NOTE:
                    successors = list(self.graph.successors(node))
                    if len(successors) == 1 and self.graph.nodes[successors[0]].get('node_type') == NodeType.NOTE:
                        # Merge the notes
                        successor = successors[0]
                        self.graph.nodes[node]['label'] += '\n' + self.graph.nodes[successor]['label']
                        # Reconnect edges
                        for succ_successor in self.graph.successors(successor):
                            self.graph.add_edge(node, succ_successor)
                        self.graph.remove_node(successor)
                        merged = True
                        break
            if not merged:
                break

    def _resolve_goto_nodes(self) -> None:
        """Replace goto nodes with direct edges"""
        for node in list(self.graph.nodes):
            if self.graph.nodes[node].get('node_type') == NodeType.GOTO:
                target_id = self.graph.nodes[node].get('target_id')
                if target_id:
                    # Add edges from predecessors to target
                    for pred in self.graph.predecessors(node):
                        self.graph.add_edge(pred, target_id)
                    self.graph.remove_node(node)

    def _flatten_containers(self) -> None:
        """Convert container relationships to node attributes"""
        # Implementation depends on how containers are represented in the graph
        pass

    def _consolidate_select_options(self) -> None:
        """Move select option information into parent node attributes"""
        # Implementation depends on how select options are represented in the graph
        pass
