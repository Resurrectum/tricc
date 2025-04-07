import networkx as nx
import re
from typing import Dict, Optional, Any
from questionnaire_parser.models.diagram import Diagram, ShapeType
from questionnaire_parser.utils.validation import (
    ValidationCollector,
    ValidationSeverity,
)
from questionnaire_parser.utils.edge_logic import EdgeLogicCalculator


class DAGConverter:
    """Converts a Draw.io diagram model into a simplified NetworkX DAG.

    This converter implements all simplification rules specified in the requirements:
    - Flag node consolidation (calculate/diagnosis → flag)
    - Type consolidation (decimal/integer → numeric)
    - Select option simplification (remove select_option nodes)
    - Container information as node attributes
    - Goto node conversion to direct edges
    - Rhombus node simplification with edge logic preservation
    - Help/hint content as node attributes
    """

    def __init__(
        self,
        diagram: Diagram,
        validation_collector: Optional[ValidationCollector] = None,
    ):
        """Initialize the converter with a parsed diagram.

        Args:
            diagram: The parsed diagram model
            validation_collector: Optional validation collector for validation issues
        """
        self.diagram = diagram
        self.validator = validation_collector or diagram.validation_collector
        self.graph = nx.DiGraph()
        self.edge_logic_calculator = EdgeLogicCalculator()

    def convert(self) -> nx.DiGraph:
        """Convert the diagram to a simplified NetworkX DAG.

        Returns:
            A NetworkX DiGraph with all simplifications applied
        """
        # Phase 1: Initial conversion
        self._initial_conversion()

        # Phase 2: Apply simplifications (except removing decision points)
        self._simplify_graph()

        # Phase 2.1: Write edge logic
        self._calculate_edge_logic()

        # Phase 3: Validate final graph
        self._validate_graph()

        return self.graph

    def _initial_conversion(self):
        """Create the initial NetworkX graph from the diagram model."""
        # Step 1: Add all nodes with basic attributes (without type inference)
        for node_id, node in self.diagram.nodes.items():
            # Base attributes for all nodes
            attrs = {
                "shape": node.shape.value,
                "label": node.label or "",
                "original_id": node_id,
                "rounded": node.style.rounded,
                "page_id": node.page_id,
                "fill_color": node.style.fill_color,  # necessary for color based diagram elements
            }

            # Add metadata if available
            if node.metadata:
                if node.metadata.name:
                    attrs["name"] = node.metadata.name

                if node.metadata.numeric_constraints:
                    attrs["min_value"] = node.metadata.numeric_constraints.min_value
                    attrs["max_value"] = node.metadata.numeric_constraints.max_value
                    attrs["constraint_message"] = (
                        node.metadata.numeric_constraints.constraint_message
                    )

            # Add options for list nodes
            if node.shape == ShapeType.LIST and node.options:
                attrs["options"] = []
                for option in node.options:
                    option_data = {"id": option.id, "label": option.label}
                    attrs["options"].append(option_data)

            # Add the node to the graph without type inference
            self.graph.add_node(node_id, **attrs)

        # Step 2: Add all edges
        for edge_id, edge in self.diagram.edges.items():
            if edge.source and edge.target:
                self.graph.add_edge(
                    edge.source, edge.target, id=edge_id, label=edge.label or ""
                )

        # Step 3: Now determine node types based on the graph structure
        self._determine_node_types()

    def _determine_node_types(self):
        """Determine node types based on graph structure and attributes."""
        for node_id in self.graph.nodes():
            shape = self.graph.nodes[node_id].get("shape")

            # Determine type based on shape and other properties
            if shape == ShapeType.RECTANGLE.value:
                self._classify_rectangle_node(node_id)
            elif shape == ShapeType.RHOMBUS.value:
                self.graph.nodes[node_id]["type"] = "decision_point"
            elif shape == ShapeType.HEXAGON.value:
                self.graph.nodes[node_id]["type"] = "integer"
            elif shape == ShapeType.ELLIPSE.value:
                self.graph.nodes[node_id]["type"] = "decimal"
            elif shape == ShapeType.CALLOUT.value:
                self.graph.nodes[node_id]["type"] = "text"
            elif shape == ShapeType.OFFPAGE.value:
                self.graph.nodes[node_id]["type"] = "goto"
            elif shape == ShapeType.LIST.value:
                self._classify_list_node(node_id)
            else:
                self.graph.nodes[node_id]["type"] = "unknown"

    def _classify_rectangle_node(self, node_id):
        """Classify a rectangle node based on edges, styles, and other properties."""
        # Check if node has rounded edges
        rounded = self.graph.nodes[node_id].get("rounded", False)

        # Check if it's a yes/no question
        outgoing_edges = list(self.graph.out_edges(node_id, data=True))
        if outgoing_edges and all(
            data.get("label", "").lower() in ("yes", "no")
            for _, _, data in outgoing_edges
        ):
            self.graph.nodes[node_id]["type"] = "select_one_yesno"
            return

        # Check if it's a help or hint node (color + no incoming edges)
        incoming_edges = list(self.graph.in_edges(node_id))
        fill_color = self.graph.nodes[node_id].get("fill_color", "")

        if len(incoming_edges) == 0:  # No incoming edges
            if self._is_color_in_range(fill_color, "green"):
                self.graph.nodes[node_id]["type"] = "help"
                return
            elif self._is_color_in_range(fill_color, "grey"):
                self.graph.nodes[node_id]["type"] = "hint"
                return

        # Handle based on rounded edges
        if rounded:
            # Check for diagnosis colors
            if self._is_color_in_range(fill_color, "red"):
                self.graph.nodes[node_id]["type"] = "diagnosis"
                self.graph.nodes[node_id]["severity"] = "SEVERE"
            elif self._is_color_in_range(
                fill_color, "orange"
            ) or self._is_color_in_range(fill_color, "yellow"):
                self.graph.nodes[node_id]["type"] = "diagnosis"
                self.graph.nodes[node_id]["severity"] = "MODERATE"
            elif self._is_color_in_range(fill_color, "green"):
                self.graph.nodes[node_id]["type"] = "diagnosis"
                self.graph.nodes[node_id]["severity"] = "BENIGN"
            else:
                # Rounded rectangle without color is calculate
                self.graph.nodes[node_id]["type"] = "calculate"
        else:
            # Default for non-rounded rectangles without special properties
            self.graph.nodes[node_id]["type"] = "note"

    def _classify_list_node(self, node_id):
        """Classify a list node as select_one or select_multiple based on rounded corners."""
        # Get the rounded attribute from the node
        rounded = self.graph.nodes[node_id].get("rounded", False)

        if rounded:
            # List node with rounded corners is select_one
            self.graph.nodes[node_id]["type"] = "select_one"
        else:
            # List node without rounded corners is select_multiple
            self.graph.nodes[node_id]["type"] = "select_multiple"

    def _is_color_in_range(self, color, color_name):
        """Check if a color falls within a named range (red, green, blue, grey, etc.).

        Args:
            color: The color to check (hex format)
            color_name: The named color range to check against

        Returns:
            True if the color is in the range, False otherwise
        """
        if not color:
            return False

        # Normalize color format
        if isinstance(color, str):
            color = color.lower()
            if color.startswith("#"):
                color = color[1:]
        else:
            return False

        # Convert 3-digit hex to 6-digit
        if len(color) == 3:
            color = "".join(c + c for c in color)

        # Simple RGB extraction
        try:
            r = int(color[0:2], 16) if len(color) >= 2 else 0
            g = int(color[2:4], 16) if len(color) >= 4 else 0
            b = int(color[4:6], 16) if len(color) >= 6 else 0
        except ValueError:
            return False

        # Color range definitions
        if color_name == "red":
            return r > 180 and g < 100 and b < 100
        elif color_name == "green":
            return r < 150 and g > 150 and b < 150
        elif color_name == "blue":
            return r < 100 and g < 150 and b > 180
        elif color_name == "grey" or color_name == "gray":
            # calculate average of RGB
            avg = (r + g + b) / 3
            # check if all colors are close to the average
            max_diff = 10
            return (
                abs(r - avg) <= max_diff
                and abs(g - avg) <= max_diff
                and abs(r - avg) <= max_diff
            )
        elif color_name == "yellow":
            return r > 180 and g > 180 and b < 100
        elif color_name == "orange":
            return r > 180 and 100 < g < 180 and b < 100
        else:
            return False

    def _simplify_graph(self):
        """Apply all simplification rules to the graph."""
        # Phase 1: Type Consolidation
        self._consolidate_flag_nodes()
        self._convert_select_one_yesno()
        self._consolidate_numeric_types()

        # Phase 2: Structural Simplifications
        self._simplify_select_options()
        self._simplify_goto_nodes()
        self._simplify_groups()  # must happen after goto simplification, because gotos can point to groups
        self._simplify_help_hint()
        # self._simplify_rhombus_nodes() # must write edge logic first

        # Phase 3: Edge Simplifications
        self._combine_successive_notes()

    def _consolidate_flag_nodes(self):
        """Merge calculate and diagnosis nodes into flag nodes."""
        # Identify nodes to update (dictionary comprehension)
        nodes_to_update = {
            node_id: {
                "type": "flag",
                "is_diagnosis": (attrs.get("type") == "diagnosis"),  # sets boolean flag
            }
            for node_id, attrs in self.graph.nodes(data=True)
            if attrs.get("type") in {"diagnosis", "calculate"}
        }

        # Apply updates
        for node_id, updates in nodes_to_update.items():
            self.graph.nodes[node_id].update(updates)

    def _convert_select_one_yesno(self):
        """Convert select_one_yesno to standard select_one with predefined options."""
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("type") == "select_one_yesno":
                # Set type to select_one
                self.graph.nodes[node_id]["type"] = "select_one"

                # Add predefined yes/no options based on outgoing edges
                options = []
                for _, target_id, edge_attrs in self.graph.out_edges(
                    node_id, data=True
                ):
                    edge_label = edge_attrs.get("label", "").strip().lower()
                    edge_id = edge_attrs.get("id", "")
                    if edge_label in ["yes", "no"] and edge_id:
                        # add the edge label as an 'option' in order to make yes/no edge look like normal select_one
                        edge_attrs["option"] = edge_label

                        options.append(
                            {
                                "id": f"{edge_id}_{edge_label}",
                                "label": edge_label,
                                "option": edge_label,
                            }
                        )

                # Assign options to the node
                self.graph.nodes[node_id]["options"] = options

    def _consolidate_numeric_types(self):
        """Consolidate integer and decimal into numeric type."""
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("type") in ["integer", "decimal"]:
                # Set type to numeric
                self.graph.nodes[node_id]["type"] = "numeric"

                # Set value_type based on original type
                value_type = "int" if attrs.get("type") == "integer" else "float"
                self.graph.nodes[node_id]["value_type"] = value_type

    def _simplify_select_options(self):
        """Remove select_option nodes and connect their edges to the parent node."""
        # Identify all select nodes and their options
        select_nodes = {}

        for node_id, attrs in self.graph.nodes(data=True):
            if (
                attrs.get("type") in ["select_one", "select_multiple"]
                and "options" in attrs
            ):
                select_nodes[node_id] = attrs["options"]

        # For each select node, create direct edges based on options
        for node_id, options in select_nodes.items():
            for option in options:
                option_id = option.get("id")
                # yes/no options don't have an ID and are already handled
                if not option_id:
                    continue

                # Find edges coming from this option
                outgoing_edges = []
                if option_id in self.graph:
                    outgoing_edges = list(self.graph.out_edges(option_id, data=True))

                # Create direct edges from select node with option info
                for _, target, edge_attrs in outgoing_edges:
                    edge_id = edge_attrs.get("id")
                    self.graph.add_edge(
                        node_id,
                        target,
                        id=edge_id,
                        option=option["label"],
                        label=edge_attrs.get("label", ""),
                    )

                # Remove the option node
                if option_id in self.graph:
                    self.graph.remove_node(option_id)

    def _simplify_groups(self):
        """Store group information as node attributes.
        The edges that were pointing to a group are redirected to the starting node in the group.
        """
        # For each group in the diagram
        for group_id, group in self.diagram.groups.items():

            # Update all contained nodes
            for node_id in group.contained_elements:
                if node_id in self.graph:
                    self.graph.nodes[node_id]["group_id"] = group_id
                    self.graph.nodes[node_id]["group_heading"] = group.label

        # Redirect edges that point to groups to the first node in the group
        for src, tgt, attrs in list(self.graph.edges(data=True)):
            # Check if target is a group
            if tgt in self.diagram.groups:
                group = self.diagram.groups[tgt]

                # Find the start node in the group (first node that's not help/hint)
                start_node = None
                for node_id in group.contained_elements:
                    if node_id in self.graph:
                        node_type = self.graph.nodes[node_id].get("type")
                        if node_type not in ["help", "hint"]:
                            start_node = node_id
                            break

                if start_node:
                    # Add direct edge to the main node
                    self.graph.add_edge(
                        src,
                        start_node,  # start_node is the new target
                        id=attrs["id"],  # Keep the same edge ID
                        label=attrs.get("label", ""),
                        original_target=tgt,
                    )

                    # Remove edge to container
                    self.graph.remove_edge(src, tgt)

    def _simplify_goto_nodes(self):
        """Convert goto nodes to direct edges."""
        # Find all goto nodes
        goto_nodes = [
            (node_id, attrs)
            for node_id, attrs in self.graph.nodes(data=True)
            if attrs.get("type") == "goto"
        ]

        for goto_id, attrs in goto_nodes:
            # Get target name from metadata
            target_name = attrs.get("name")
            if not target_name:
                continue

            # Find target node by name
            target_id = next(
                (
                    n_id
                    for n_id, n_attrs in self.graph.nodes(data=True)
                    if n_attrs.get("name") == target_name
                ),
                None,
            )
            if not target_id:
                continue

            # Redirect incoming edges to the target node
            for src, _, edge_attrs in list(self.graph.in_edges(goto_id, data=True)):
                self.graph.add_edge(src, target_id, **edge_attrs)
                self.graph.remove_edge(src, goto_id)

            # Remove goto node
            self.graph.remove_node(goto_id)

    def _simplify_rhombus_nodes(self):
        """Replace decision point nodes by edges with combined edge logic."""
        # Find all decision point nodes
        decision_points = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("type") == "decision_point":
                decision_points.append((node_id, attrs))

        for decision_point_id, attrs in decision_points:
            # Skip external decision points
            if attrs.get("external", False):
                continue

            # Get referenced node name
            ref_name = attrs.get("name")
            if not ref_name:
                continue

            # Find referenced node
            ref_id = None
            for n_id, n_attrs in self.graph.nodes(data=True):
                if n_attrs.get("name") == ref_name:
                    ref_id = n_id
                    break

            if not ref_id:
                continue

            # Get incoming and outgoing edges
            incoming_edges = list(self.graph.in_edges(decision_point_id, data=True))
            outgoing_edges = list(self.graph.out_edges(decision_point_id, data=True))

            # Create direct edges which have as source the source of the incoming edge,
            # and as target the target of the ougoing edge,
            # short-cuting the path over the decision point.
            # The new edge holds the combined logic of the edges it replaces
            for src, _, in_attrs in incoming_edges:
                for _, tgt, out_attrs in outgoing_edges:
                    # Skip if the edge already exists
                    if self.graph.has_edge(src, tgt):
                        continue

                    # Create condition based on decision point
                    condition = self._create_decision_condition(
                        decision_point_id, ref_id, attrs, out_attrs.get("label", "")
                    )

                    # Add new edge
                    self.graph.add_edge(
                        src,
                        tgt,
                        id=f"{src}_{tgt}",
                        label=out_attrs.get("label", ""),
                        condition=condition,
                        via_decision=decision_point_id,
                    )

            # Remove decision point node
            self.graph.remove_node(decision_point_id)

    def _create_decision_condition(
        self,
        decision_point_id: str,
        ref_id: str,
        decision_attrs: Dict[str, Any],
        edge_label: str,
    ) -> Dict[str, Any]:
        """Create a logical condition for a decision point node."""
        ref_attrs = self.graph.nodes[ref_id]
        ref_type = ref_attrs.get("type", "")
        decision_label = decision_attrs.get("label", "")

        # Base condition structure
        condition = {
            "type": "condition",
            "node": ref_id,
            "operator": "=",
            "value": edge_label == "Yes",  # True if Yes, False if No
        }

        # Type-specific condition handling
        if ref_type in ["numeric", "integer", "decimal"]:
            # Parse equation from decision label
            match = re.search(r"(.*?)(\s*[=<>]=?\s*)(\d+(?:\.\d+)?)", decision_label)
            if match:
                _, operator, value = match.groups()
                condition["operator"] = operator.strip()
                condition["value"] = float(value)

        elif ref_type == "select_multiple":
            # Extract option from square brackets
            match = re.search(r"\[(.*?)\]", decision_label)
            if match:
                option = match.group(1)
                condition["operator"] = "contains"
                condition["value"] = option

        return condition

    def _simplify_help_hint(self):
        """Store help/hint content as node attributes."""
        # Find all help/hint nodes
        help_hint_nodes = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("type") in ["help", "hint"]:
                help_hint_nodes.append((node_id, attrs))

        for help_id, attrs in help_hint_nodes:
            node_type = attrs.get("type")
            label = attrs.get("label", "")

            # Find associated nodes by looking at outgoing edges
            associated_nodes = []
            for _, target_id in self.graph.out_edges(help_id):
                associated_nodes.append(target_id)

            if not associated_nodes:
                # If no outgoing edges, skip this help/hint node
                continue

            # Add help/hint text to all associated nodes
            attr_name = "help_text" if node_type == "help" else "hint_text"
            for main_node in associated_nodes:
                self.graph.nodes[main_node][attr_name] = label

            # Remove help/hint node
            self.graph.remove_node(help_id)

    def _combine_successive_notes(self):
        """Combine successive note nodes into a single node."""
        # Keep combining notes until no more combinations are possible
        while True:
            # Find a pair of notes to combine
            found_pair = False

            for node_id, attrs in list(self.graph.nodes(data=True)):
                # Skip if not a note
                if attrs.get("type") != "note":
                    continue

                # Check outgoing edges
                successors = list(self.graph.successors(node_id))
                if len(successors) != 1:
                    continue

                succ = successors[0]

                # Check if successor is a note with only this incoming edge
                if (
                    self.graph.nodes.get(succ, {}).get("type") == "note"
                    and len(list(self.graph.predecessors(succ))) == 1
                ):

                    # Combine the successor's content into this node
                    current_label = attrs.get("label", "")
                    succ_label = self.graph.nodes[succ].get("label", "")
                    self.graph.nodes[node_id][
                        "label"
                    ] = f"{current_label}\n\n{succ_label}"

                    # Redirect edges from successor to this node
                    for _, target, edge_attrs in list(
                        self.graph.out_edges(succ, data=True)
                    ):
                        self.graph.add_edge(
                            node_id,
                            target,
                            id=f"{node_id}_{target}",
                            label=edge_attrs.get("label", ""),
                        )

                    # Remove the successor
                    self.graph.remove_node(succ)

                    found_pair = True
                    break

            # If no more pairs can be combined, we're done
            if not found_pair:
                break

    def _validate_graph(self):
        """Validate the final graph structure."""
        # Check if it's a DAG
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))

            if self.validator:
                message = f"Graph contains cycles after simplification: {cycles}"
                self.validator.add_result(
                    severity=ValidationSeverity.CRITICAL,
                    message=message,
                    element_type="Graph",
                )
            else:
                raise ValueError(
                    f"Graph contains cycles after simplification: {cycles}"
                )

        # Check for isolated nodes
        isolated = [node for node in self.graph.nodes() if self.graph.degree(node) == 0]

        if isolated and self.validator:
            message = f"Graph contains isolated nodes after simplification: {isolated}"
            self.validator.add_result(
                severity=ValidationSeverity.WARNING,
                message=message,
                element_type="Graph",
            )

        # Check for dangling edges
        dangling = []
        for src, tgt in self.graph.edges():
            if src not in self.graph or tgt not in self.graph:
                dangling.append((src, tgt))

        if dangling and self.validator:
            message = f"Graph contains dangling edges after simplification: {dangling}"
            self.validator.add_result(
                severity=ValidationSeverity.ERROR, message=message, element_type="Graph"
            )

    def _calculate_edge_logic(self):
        """Calculate and attach logic to all edges in the graph based on their source node type."""
        for source_id, target_id, edge_attrs in self.graph.edges(data=True):
            # Skip if source doesn't exist (shouldn't happen with validation)
            if source_id not in self.graph.nodes:
                continue

            # Get source node type
            source_type = self.graph.nodes[source_id].get("type")

            # Get source node label
            source_label = self.graph.nodes[source_id].get("label", "")

            # Skip node types that don't have direct logic
            if source_type in ["note", "numeric", "text", "help", "hint"]:
                continue

            # Calculate logic using the edge logic calculator
            logic = self.edge_logic_calculator.calculate_edge_logic(
                source_label, source_type, source_id, edge_attrs
            )

            # Calculate decision point logic
            if source_type == "decision_point":
                # Get source reference node
                reference_name = self.graph.nodes[source_id].get("name", "")
                # Get ID of node where name = reference_name and that is not a decision point
                reference_id = next(
                    (
                        node_id
                        for node_id, attrs in self.graph.nodes(data=True)
                        if attrs.get("name") == reference_name
                        and attrs.get("type") != "decision_point"
                    ),
                    None,
                )
                if reference_id:
                    reference_type = self.graph.nodes[reference_id].get("type", "")
                elif (
                    reference_name
                    in self.diagram.allowed_externals.get_flag_references()
                ):
                    reference_type = "flag"
                elif (
                    reference_name
                    in self.diagram.allowed_externals.get_numeric_references()
                ):
                    reference_type = "numeric"
                else:
                    reference_type = "unknown"

                logic = self.edge_logic_calculator.calculate_decision_point_logic(
                    reference_type,
                    source_label,
                    edge_attrs.get("label", ""),
                    reference_id,
                )

            # If logic was generated, attach it to the edge
            if logic:
                edge_attrs["logic"] = logic.to_dict()
