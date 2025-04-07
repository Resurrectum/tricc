"""
Module for calculating edge logic in medical questionnaire diagrams.

This module implements the rules from the Edge Logic Calculation Rules document,
handling how edge logic is determined based on the source node type.
"""

import re
from typing import Dict, Any, Optional, Tuple


class EdgeLogic:
    """Represents a logical condition for an edge."""

    def __init__(self, type_: str, **kwargs):
        """Initialize the edge logic.

        Args:
            type_: 'condition' or 'operator'
            **kwargs: Additional attributes based on type
                For 'condition': node, operator, value
                For 'operator': operation, conditions
        """
        self.type = type_
        self.attributes = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Convert the edge logic to a dictionary representation."""
        result = {"type": self.type}
        result.update(self.attributes)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EdgeLogic":
        """Create an EdgeLogic object from a dictionary."""
        type_ = data.pop("type")
        return cls(type_, **data)

    @classmethod
    def and_conditions(cls, *conditions: "EdgeLogic") -> "EdgeLogic":
        """Combine multiple conditions with AND logic."""
        if len(conditions) == 1:
            return conditions[0]
        return cls("operator", operation="AND", conditions=list(conditions))

    @classmethod
    def or_conditions(cls, *conditions: "EdgeLogic") -> "EdgeLogic":
        """Combine multiple conditions with OR logic."""
        if len(conditions) == 1:
            return conditions[0]
        return cls("operator", operation="OR", conditions=list(conditions))


class EdgeLogicCalculator:
    """Calculates the logical conditions for edges in the questionnaire graph.

    This class implements the rules from the Edge Logic Calculation Rules document,
    handling the calculation of edge logic based on source node type, edge attributes,
    and referenced nodes.
    """

    def calculate_edge_logic(
        self, node_label: str, node_type: str, node_id: str, edge_attrs: Dict[str, Any]
    ) -> Optional[EdgeLogic]:
        """Calculate edge logic based on source node type and edge attributes.

        Args:
            node_type: Type of the source node ('select_one', 'select_multiple', etc.)
            node_id: ID of the source node
            edge_attrs: Edge attributes, including label

        Returns:
            EdgeLogic object representing the condition, or None if no logic applies
        """
        # Get essential edge attributes
        edge_label = edge_attrs.get("label", "")
        option = edge_attrs.get("option", None)

        # Calculate logic based on type of originating node
        if node_type == "select_one":
            return self._select_one_logic(node_id, option, edge_label)
        elif node_type == "select_multiple":
            return self._select_multiple_logic(node_id, option)
        elif node_type == "flag":
            return self._flag_logic(node_label)
        else:
            # Direct edges from numeric, text, note, don't carry logic and
            # edges from decision points are handled separately
            return None

    def calculate_decision_point_logic(
        self,
        reference_type: str,
        decision_label: str,
        edge_label: str,
        reference_id: Optional[str] = None,
    ) -> EdgeLogic:
        """Calculate logic for a decision point (rhombus) reference.

        Args:
            reference_id: ID of the node being referenced
            reference_type: Type of the referenced node
            decision_label: Label of the decision point/rhombus
            edge_label: Label of the edge from the decision point

        Returns:
            EdgeLogic object representing the decision condition
        """
        # For flag reference in decision point
        if reference_type == "flag":
            return self._flag_logic(decision_label, edge_label)

        # Select one reference in decision point
        elif reference_type == "select_one":
            return self._select_one_logic(reference_id, decision_label, edge_label)

        # Select multiple reference in decision point
        elif reference_type == "select_multiple":
            # Extract option from brackets in decision label
            option = self._extract_option_from_label(decision_label)
            if option:
                return self._select_multiple_logic(reference_id, option)

            # Fallback to basic condition if parsing fails
            return EdgeLogic(
                "condition",
                node=reference_id,
                operator="=",
                value=edge_label.lower() == "yes",
            )

        # Numeric reference (parse equation from label)
        elif reference_type == "numeric":
            operator, value = self._parse_numeric_condition(decision_label)
            if operator and value is not None:
                # For "No" edge, negate the operator
                if edge_label.lower() == "no":
                    operator = self._negate_operator(operator)

                return EdgeLogic(
                    "condition", variable=reference_id, operation=operator, value=value
                )

            # Fallback if parsing fails
            return EdgeLogic(
                "condition",
                variable=reference_id,
                operation="=",
                value=(edge_label.lower() == "yes"),
            )

        # Select multiple reference (extract option from brackets)
        elif reference_type == "select_multiple":
            option = self._extract_option_from_label(decision_label)
            if option and edge_label.lower() == "yes":
                return EdgeLogic(
                    "condition", node=reference_id, operator="contains", value=option
                )
            elif option and edge_label.lower() == "no":
                return EdgeLogic(
                    "condition",
                    node=reference_id,
                    operator="not contains",
                    value=option,
                )
            # Fallback to basic condition if parsing fails
            return EdgeLogic(
                "condition",
                node=reference_id,
                operator="=",
                value=edge_label.lower() == "yes",
            )

        # Default case - simple yes/no logic
        return EdgeLogic(
            "condition",
            node=reference_id,
            operator="=",
            value=edge_label.lower() == "yes",
        )

    def _negate_operator(self, operator: str) -> str:
        """Negate a comparison operator.

        Args:
            operator: The operator to negate

        Returns:
            The negated operator
        """
        negation_map = {
            "=": "!=",
            "!=": "=",
            ">": "<=",
            "<": ">=",
            ">=": "<",
            "<=": ">",
        }
        return negation_map.get(operator, operator)

    def combine_path_logic(
        self, source_logic: Optional[EdgeLogic], added_logic: Optional[EdgeLogic]
    ) -> Optional[EdgeLogic]:
        """Combine existing path logic with new edge logic.

        Args:
            source_logic: Existing logic from the path so far
            added_logic: New logic to add from the current edge

        Returns:
            Combined logic, or None if both inputs are None
        """
        if not source_logic:
            return added_logic
        if not added_logic:
            return source_logic

        return EdgeLogic.and_conditions(source_logic, added_logic)

    def _select_one_logic(
        self, node_id: str, option: str, edge_label: str
    ) -> EdgeLogic:
        """Calculate logic for select_one node edges.
        If option is missing, a yes/no question is assumed.
        """
        if edge_label.lower() == "yes":
            return EdgeLogic("condition", node=node_id, operator="=", value=option)
        elif edge_label.lower() == "no":
            return EdgeLogic("condition", node=node_id, operator="!=", value=option)
        else:
            return None

    def _select_multiple_logic(self, node_id: str, option: str) -> EdgeLogic:
        """Calculate logic for select_multiple node edges."""
        return EdgeLogic("condition", node=node_id, operator="contains", value=option)

    def _flag_logic(
        self, flag_label: str, edge_label: Optional[str] = None
    ) -> Optional[EdgeLogic]:
        """Calculate logic for edges originating from flag nodes."""

        # Create condition to check if this flag exists in the 'flags' set
        if not edge_label or edge_label.lower() == "yes":
            return EdgeLogic(
                "condition",
                variable="flags",  # Reference the global flags set
                operation="in",  # Check if value is in the set
                value=flag_label,
            )  # The flag label to check for
        elif edge_label.lower() == "no":
            return EdgeLogic(
                "condition",
                variable="flags",  # Reference the global flags set
                operation="not in",  # Check if value is not in the set
                value=flag_label,
            )
        else:
            return None

    def _parse_numeric_condition(
        self, label: str
    ) -> Tuple[Optional[str], Optional[float]]:
        """Parse numeric condition from decision point label.

        Args:
            label: Label text containing the condition

        Returns:
            Tuple of (operator, value), or (None, None) if parsing fails
        """
        # Match patterns like "Age > 5", "Temperature >= 37.5", etc.
        pattern = r"(.*?)(?:\s*)([=<>!]=|[<>])(?:\s*)(\d+(?:\.\d+)?)"
        match = re.search(pattern, label)

        if match:
            # Extract the operator and value
            _, operator, value_str = match.groups()
            try:
                value = float(value_str)
                # Convert to integer if it's a whole number
                if value.is_integer():
                    value = int(value)
                return operator.strip(), value
            except ValueError:
                pass

        return None, None

    def _extract_option_from_label(self, label: str) -> Optional[str]:
        """Extract option name from square brackets in label.

        Args:
            label: Label text containing bracketed option

        Returns:
            Option text, or None if no bracketed text found
        """
        # Match text within square brackets [like this]
        match = re.search(r"\[(.*?)\]", label)
        if match:
            return match.group(1).strip()
        return None
