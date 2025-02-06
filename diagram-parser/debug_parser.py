# diagram-parser/debug_parser.py
import logging
from pathlib import Path
from questionnaire_parser.core.parser import DrawIoParser
from questionnaire_parser.utils.debugging import DiagramDebugger

def main():
    # Configure logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    # File paths
    input_file = Path("diagram-parser/examples/dx_without_pictures.drawio")
    
    try:
        # Parse diagram
        logger.info(f"Parsing file: {input_file}")
        parser = DrawIoParser()
        diagram = parser.parse_file(input_file)
        
        # Initialize debugger
        debugger = DiagramDebugger(diagram=diagram)
        
        # Generate visualization
        debugger.visualize_graph("debug_output/graph_visualization.png")
        
        # Print statistics
        debugger.print_graph_stats()
        
        # Analyze specific nodes (replace with actual node IDs from your diagram)
        start_node = "node_1"  # Update with real ID
        debugger.analyze_node(start_node)
        
    except Exception as e:
        logger.exception("Error during parsing")
        raise

if __name__ == "__main__":
    main()