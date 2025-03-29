# Medical Questionnaire System: Design Documentation

## 1. Overview

This document outlines the design for converting draw.io medical questionnaire diagrams into interactive HTML forms. The system follows a pipeline approach, transforming the visual representation of a medical decision tree into a functional, dynamic questionnaire.

## 2. Data Model

### 2.1 Form Data Storage

Patient responses are stored in a structured format that aligns with question types:

| Node Type | Storage Format | Example | Comment |
|-----------|----------------|---------|---------|
| Flags | Set | `flags = {"hypertension", "diabetes"}` | All flags are stored in one set |
| Select Multiple | List/Array | `symptoms = ["fever", "cough"]` | Each Node is stored in its own list |
| Select One | String | `gender = "male"` | ... |
| Numeric | int/float | `age = 6` | ... |
| Yes/No | Boolean | `has_pain = true` | ... |

### 2.2 Node Types and Representations

The system supports multiple question types, each with distinct visual representations in the diagram:

- **Select One**: List node with rounded corners
- **Select Multiple**: List node with sharp corners
- **Numeric**: Hexagon (integer) or ellipse (decimal) shapes
- **Yes/No**: Rectangle with Yes/No outgoing edges
- **Flag/Diagnosis**: Rounded rectangle, the flags are transparent, the diagnosis use color-coding for severity
- **Note**: Standard rectangle
- **Text**: Call out shape
- **Rhombus**: Decision point referencing other nodes or external data

## 3. Logic Representation

We use a dictionary-based structure to encode the logic. It is easily serializable to JSON:

### 3.1 Basic Condition Structure

```python
{
    "type": "condition",
    "node_id": str,  # ID of the node being referenced
    "operation": str,  # "=", ">", "<", ">=", "<=", "!=", "in"
    "value": Any  # The value to compare against
}
```

### 3.2 Compound Logic Structure

```python
{
    "type": "operator",
    "operation": str,  # "AND", "OR", "NOT"
    "conditions": list  # List of condition objects or nested operators
}
```

### 3.3 Edge Logic

Edge logic defines the conditions for traversing from one node to another. It represents the condition that must be fulfilled to activate this path. It relates only to the node that the edge originates from. If the user wishes to define a more complex logic, additional `decision point` nodes must be included into the path.  

#### 3.3.1 Edge Logic by Node Type

##### Select Multiple

```python
# Edge from a "Fever" option of a symptoms list
{
    "type": "condition",
    "node_id": "symptoms",
    "operation": "in",
    "value": "Fever"
}
```

##### Select One

```python
# Edge from "Male" option
{
    "type": "condition",
    "node_id": "gender",
    "operation": "=",
    "value": "Male"
}
```

##### Yes/No Question

```python
# Edge from "Yes" path
{
    "type": "condition",
    "node_id": "has_pain",
    "operation": "=",
    "value": True
}
```

##### Numeric (Only possible from a Decision Point)

```python
# Path for age >= 18
{
    "type": "condition",
    "node_id": "age",
    "operation": ">=",
    "value": 18
}
```

##### Flag Nodes

```python
# Checking if a diagnosis/flag is set
{
    "type": "condition",
    "node_id": "flags",
    "operation": "in",
    "value": "hypertension"
}
```

##### Combined Logic, as defined in 3.2

```python
# Adult AND has fever
{
    "type": "operator",
    "operation": "AND",
    "conditions": [
        {
            "type": "condition",
            "node_id": "age",
            "operation": ">=",
            "value": 18
        },
        {
            "type": "condition",
            "node_id": "symptoms",
            "operation": "in",
            "value": "Fever"
        }
    ]
}
```
### 3.4 Node Logic
Node logic defines the condition for display a node element. It is obtained by combining the logic of all incoming edges wit `OR`. 

## 4. Processing Pipeline

### 4.1 Diagram to HTML Workflow

```
Draw.io XML → Parser → NetworkX Graph → Apply Simplifications → HTML Generator
```

1. **Parse Diagram**: Convert draw.io XML to diagram model
2. **Create NetworkX Graph**: Transform diagram into directed graph
3. **Generate Edge Logic**: Create edge logic
4. **Apply Simplifications**: Optimize graph structure
5. **Generate Node Logic**: Create node logic
6. **Generate HTML**: Create interactive questionnaire form

### 4.2 Graph Simplification Rules

The system applies several simplification rules to optimize the graph:

1. **Type Consolidation**:
   - Merge `calculate` and `diagnosis` into a single `flag` type
   - Convert `select_one yesno` to standard `select_one` with predefined options
   - Consolidate numeric types (`decimal`, `integer` → `numeric`)

2. **Structural Simplifications**:
   - Remove `select_option` nodes and connect their outgoing edges to the parent
   - Store group information as node attributes
   - Convert goto nodes to direct edges
   - Replace rhombus nodes with direct edges carrying combined logic. Every edge pointing to the rhombus is replaced by the amount of edges that originate from the rhombus. 
   - Store help/hint content as node attributes

3. **Edge Simplifications**:
   - Combine successive notes, if possible. 
   - Simplify edge logic in order to shorten the length of the logic expression

### 4.3 Node Logic Generation

The system generates "node logic" that determines when each question should be displayed:

1. **Identify Paths**: For each node, identify all possible paths to reach it
2. **Extract Conditions**: Gather edge logic from all incoming paths
3. **Combine with OR**: Different paths represent alternative ways to reach the node
4. **Simplify**: Apply logic simplification to the combined conditions

```python
# Example node logic for showing a question
{
    "type": "operator",
    "operation": "OR",
    "conditions": [
        # Path 1 conditions (e.g., adult with fever)
        {
            "type": "operator",
            "operation": "AND",
            "conditions": [...]
        },
        # Path 2 conditions (e.g., child with severe symptoms)
        {
            "type": "operator",
            "operation": "AND",
            "conditions": [...]
        }
    ]
}
```

## 5. HTML Form Generation

### 5.1 Form Structure

The generated HTML form will:
- Include all questions as DOM elements
- Set initial visibility based on starting nodes
- Use JavaScript to manage question flow
- Store responses in the defined data format
- Validate inputs based on constraints

### 5.2 JavaScript Logic Evaluation

```javascript
// Evaluate if a question should be shown
function evaluateLogic(logic, formData) {
    if (!logic) return true;
    
    if (logic.type === "condition") {
        const value = formData[logic.node_id];
        
        switch(logic.operation) {
            case "=": return value === logic.value;
            case ">": return value > logic.value;
            case ">=": return value >= logic.value;
            case "<": return value < logic.value;
            case "<=": return value <= logic.value;
            case "!=": return value !== logic.value;
            case "in": 
                if (logic.node_id === "flags") {
                    return formData.flags && formData.flags.has(logic.value);
                }
                return Array.isArray(value) && value.includes(logic.value);
        }
    } 
    else if (logic.type === "operator") {
        const conditions = logic.conditions || [];
        
        if (logic.operation === "AND") {
            return conditions.every(c => evaluateLogic(c, formData));
        } 
        else if (logic.operation === "OR") {
            return conditions.some(c => evaluateLogic(c, formData));
        }
        else if (logic.operation === "NOT") {
            return !evaluateLogic(conditions[0], formData);
        }
    }
    
    return true;
}

// Update form visibility based on current answers
function updateFormVisibility() {
    const formData = collectFormData();
    
    // For each question in the form
    for (const questionId in questionLogic) {
        const shouldShow = evaluateLogic(questionLogic[questionId], formData);
        document.getElementById(questionId).style.display = shouldShow ? "block" : "none";
    }
}
```

### 5.3 Form Interaction Flow

1. User loads the form with initial questions visible
2. Each user response triggers:
   - Storage of the answer in the form data
   - Re-evaluation of all question visibility rules
   - Showing/hiding questions based on the updated data
3. Flag nodes are automatically processed when their conditions are met
4. Diagnosis results can be displayed based on activated flags

## 6. Logic Simplification Strategies

The system applies several optimization strategies:

### 6.1 Numeric Range Simplification

- `age > 5 AND age > 10` → `age > 10`
- `age < 10 AND age > 5` → `5 < age < 10`
- `age >= 18 OR age >= 21` → `age >= 18`

### 6.2 Set Operation Simplification

- `"fever" in symptoms AND "cough" in symptoms` → both in symptoms
- `"fever" in symptoms OR "rash" in symptoms` → either in symptoms

### 6.3 Boolean Simplification

- `pain = true AND pain = true` → `pain = true`
- `gender = "male" OR gender = "male"` → `gender = "male"`
- `condition1 AND (condition1 OR condition2)` → `condition1`

## 7. Edge Cases and Considerations

### 7.1 Form State Management

- Patient data persists throughout the form process
- All previously answered questions remain in memory
- Changing an answer may affect visibility of multiple questions

### 7.2 Flag Processing

- Flags are not directly answered by users
- They're activated automatically when a path traverses through a flag node
- Multiple flags can be active simultaneously
- Flags can trigger diagnoses with different severity levels

### 7.3 External References

- Some decision points may reference external systems or data
- These are handled as a special case with allowlist validation

## 8. Next Steps

1. Implement the DAGConverter with proper edge logic generation
2. Create the HTML generator component
3. Develop a JavaScript framework for dynamic questionnaire behavior
4. Implement testing and validation for the form logic