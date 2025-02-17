# Draw.io Medical Questionnaire Parser

## Overview

This parser converts draw.io medical questionnaire diagrams into a NetworkX graph representation. It implements a multi-pass parsing strategy to handle complex dependencies between different element types.

## Implementation Details

### Core Components

1. **Base Models** (`diagram.py`)
   - `Node`: Represents questionnaire nodes (questions, calculations, etc.)
   - `Edge`: Represents connections between nodes
   - `Group`: Represents grouped elements
   - `Diagram`: Top-level container for all elements

2. **Parser** (`parser.py`)
   - Implements multi-pass parsing strategy
   - Handles draw.io XML format
   - Creates diagram model objects

### Parsing Strategy

The parser implements a four-pass strategy to handle element dependencies:

1. **First Pass: Groups**
   - Identifies and creates group containers
   - Groups must be created first as other elements may reference them
   - Groups are identified by:
     - vertex=1 in attributes
     - swimlane in style
     - No childLayout attribute

2. **Second Pass: List Nodes**
   - Creates multiple choice question nodes
   - Adds them to parent groups if applicable
   - List nodes are identified by:
     - vertex=1 in attributes
     - swimlane in style
     - childLayout=stackLayout

3. **Third Pass: Regular Nodes**
   - Creates all other node types (including rhombus)
   - Handles node-specific attributes
   - Processes select options for list nodes
   - Node types determined by shape:
     - Rectangle (default)
     - Hexagon (numeric input)
     - Ellipse (decimal input)
     - Rhombus (condition)
     - Callout (text)
     - OffPage (goto)

4. **Fourth Pass: Edges**
   - Creates connections between nodes
   - Validates source and target references
   - Handles edge attributes and styling

### Shape Detection

Shapes are determined through style attributes:

```python
def _determine_shape(self, cell: ET.Element) -> ShapeType:
    style = self._parse_style_string(cell.get('style', ''))

    for shape_type in ShapeType:
        # Skip list and rectangle as they are not stored in the style dict
        if shape_type in (ShapeType.LIST, ShapeType.RECTANGLE):
            continue
        
        # Check both direct style and shape= format
        if shape_type in style.keys() or style.get('shape') == shape_type:
            return shape_type
            
    return ShapeType.RECTANGLE
```

### Validation

Validation occurs at multiple levels:

1. **Element Level**
   - Basic attribute validation
   - Type-specific requirements
   - Geometry validation

2. **Relationship Level**
   - Parent-child relationships
   - Edge connections
   - Group membership

3. **Diagram Level**
   - Overall structure validation
   - DAG properties
   - Business rules

### Error Handling

The parser implements flexible error handling:

1. **Validation Levels**
   - STRICT: Raises all validation errors
   - NORMAL: Raises critical errors, warns on others
   - LENIENT: Only warns, never raises

2. **Error Classification**
   - Critical: Must raise (e.g., malformed XML)
   - Error: Configurable (e.g., missing edge target)
   - Warning: Log only (e.g., style inconsistencies)

## Usage

Basic usage:

```python
from questionnaire_parser import DrawIoParser, ValidationLevel

# Create parser with desired validation level
parser = DrawIoParser(validation_level=ValidationLevel.NORMAL)

# Parse diagram
diagram, validation_results = parser.parse_file('questionnaire.drawio')

# Check for validation issues
for result in validation_results:
    print(f"{result.severity}: {result.message}")
```

## Element Attributes

### Nodes

1. **Base Attributes**
   - id: Unique identifier
   - label: Display text
   - page_id: draw.io page reference
   - metadata: Additional information

2. **Visual Properties**
   - shape: Node shape type
   - geometry: Position and size
   - style: Visual styling

### Edges

1. **Required Attributes**
   - source: Source node ID
   - target: Target node ID

2. **Optional Attributes**
   - label: Edge label
   - style: Visual styling

### Groups

1. **Core Attributes**
   - contained_elements: Set of contained node IDs
   - geometry: Position and size

## Implementation Notes

1. **XML Parsing**
   - Uses lxml for efficient XML processing
   - Maintains original tree structure
   - Uses native iteration with `iter()`

2. **Memory Management**
   - Minimizes intermediate data structures
   - Uses references instead of copies
   - Efficient collection types

3. **Performance**
   - Multi-pass approach prioritizes correctness
   - Efficient node type determination
   - Minimal tree traversals

## Limitations

1. Current implementation:
   - Requires valid draw.io XML
   - Assumes single entry point
   - Limited support for custom shapes

2. Validation:
   - Some validations only occur after full parsing
   - Complex relationships may need manual verification
   - Custom validation rules may be needed

## Future Improvements

1. Planned enhancements:
   - Enhanced error visualization
   - Automatic diagram repair
   - Performance optimizations

2. Potential features:
   - Custom shape support
   - Alternative output formats
   - Interactive validation