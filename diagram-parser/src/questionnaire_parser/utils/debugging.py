import logging
from typing import Any, Dict, Optional
import networkx as nx
import matplotlib.pyplot as plt
from questionnaire_parser.models.diagram import Diagram, NodeType

class DebugLogger:
    """Handles debug logging for the questionnaire parser"""
    
    def __init__(self, log_level: int = logging.DEBUG):
        # Set up logging with detailed formatting
        self.logger = logging.getLogger('questionnaire_parser')
        self.logger.setLevel(log_level)
        
        # Create console handler with formatting
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log_node_processing(self, node_id: str, node_data: Dict[str, Any]):
        """Log detailed information about node processing"""
        self.logger.debug(f"Processing node {node_id}")
        self.logger.debug(f"Node type: {node_data.get('node_type')}")
        self.logger.debug(f"Node attributes: {node_data}")

    def log_edge_processing(self, edge_id: str, source: str, target: str):
        """Log information about edge processing"""
        self.logger.debug(f"Processing edge {edge_id}")
        self.logger.debug(f"Edge connects: {source} -> {target}")

class DiagramDebugger:
    """Provides debugging utilities for diagram visualization and analysis"""
    
    def __init__(self, diagram: Optional[Diagram] = None, graph: Optional[nx.DiGraph] = None):
        self.diagram = diagram
        self.graph = graph
        self.logger = DebugLogger()

    def visualize_graph(self, output_file: str = "debug_graph.png"):
        """Generate a visual representation of the graph"""
        if not self.graph:
            raise ValueError("No graph available for visualization")
            
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(self.graph)
        
        # Draw nodes with different colors based on type
        node_colors = self._get_node_colors()
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors)
        nx.draw_networkx_edges(self.graph, pos)
        nx.draw_networkx_labels(self.graph, pos)
        
        plt.savefig(output_file)
        plt.close()

    def _get_node_colors(self) -> list:
        """Assign colors to nodes based on their type"""
        color_map = {
            NodeType.SELECT_ONE: 'skyblue',
            NodeType.SELECT_MULTIPLE: 'lightgreen',
            NodeType.NOTE: 'yellow',
            NodeType.RHOMBUS: 'orange',
            NodeType.INTEGER: 'pink',
            NodeType.DECIMAL: 'purple',
            NodeType.FLAG: 'red'
        }
        
        return [color_map.get(self.graph.nodes[node].get('node_type'), 'gray') 
                for node in self.graph.nodes]

    def print_graph_stats(self):
        """Print statistical information about the graph"""
        if not self.graph:
            raise ValueError("No graph available for analysis")
            
        print("\nGraph Statistics:")
        print(f"Number of nodes: {self.graph.number_of_nodes()}")
        print(f"Number of edges: {self.graph.number_of_edges()}")
        print(f"Is DAG: {nx.is_directed_acyclic_graph(self.graph)}")
        
        # Node type distribution
        type_count = {}
        for node in self.graph.nodes:
            node_type = self.graph.nodes[node].get('node_type')
            type_count[node_type] = type_count.get(node_type, 0) + 1
        
        print("\nNode type distribution:")
        for node_type, count in type_count.items():
            print(f"{node_type}: {count}")

    def trace_path(self, start_node: str, end_node: str):
        """Trace and print all paths between two nodes"""
        if not self.graph:
            raise ValueError("No graph available for path tracing")
            
        try:
            paths = list(nx.all_simple_paths(self.graph, start_node, end_node))
            print(f"\nPaths from {start_node} to {end_node}:")
            for i, path in enumerate(paths, 1):
                print(f"\nPath {i}:")
                for node in path:
                    node_data = self.graph.nodes[node]
                    print(f"  Node: {node}")
                    print(f"  Type: {node_data.get('node_type')}")
                    print(f"  Label: {node_data.get('label', '')}")
        except nx.NetworkXNoPath:
            print(f"No path exists between {start_node} and {end_node}")

    def analyze_node(self, node_id: str):
        """Print detailed analysis of a specific node"""
        if not self.graph or node_id not in self.graph:
            raise ValueError(f"Node {node_id} not found in graph")
            
        node_data = self.graph.nodes[node_id]
        print(f"\nNode Analysis for {node_id}:")
        print(f"Type: {node_data.get('node_type')}")
        print(f"Label: {node_data.get('label', '')}")
        print(f"Incoming edges: {list(self.graph.predecessors(node_id))}")
        print(f"Outgoing edges: {list(self.graph.successors(node_id))}")
        
        if node_data.get('node_type') in [NodeType.SELECT_ONE, NodeType.SELECT_MULTIPLE]:
            print("Options:", node_data.get('options', []))
