from questionnaire_parser.utils.validation import ValidationSeverity

class EdgeValidationErrorHandler:
    """Handles edge validation errors from the model validation."""

    def __init__(self, validation_collector, diagram=None):
        self.validator = validation_collector
        self.diagram = diagram

    def set_diagram(self, diagram):
        """Set the diagram reference for context in error messages."""
        self.diagram = diagram

    def handle_edge_error(self, validation_error):
        """Process validation errors from the model and add context.
        
        Args:
            validation_error: A Pydantic ValidationError
            edge_data: The edge data that failed validation
            cell_id: The ID of the cell being processed
        """
        for error in validation_error.errors():
            error_type = error.get('type')

            if error_type == 'ghost-edge':
                self._handle_ghost_edge(error)
            elif error_type == 'target-missing':
                self._handle_missing_target(error)
            elif error_type == 'source-missing':
                self._handle_missing_source(error)

    def _handle_ghost_edge(self, error):
        """Handle edges with both source and target missing."""
        self.validator.add_result(
            severity=ValidationSeverity.WARNING,
            message=error.get('msg', 'Ghost edge found'),
            element_id=error['input']['id'],
            element_type='Edge',
            field_name='endpoints'
        )

    def _handle_missing_target(self, error):
        """Handle edges with missing target."""
        source_info = self._set_element_info(error['input']['source'], 'source')
        message = f"{error.get('msg', 'Edge has no target')}.{source_info}"

        self.validator.add_result(
            severity=ValidationSeverity.ERROR,
            message=message,
            element_id=error['input']['id'],
            element_type='Edge',
            field_name='target'
        )

    def _handle_missing_source(self, error):
        """Handle edges with missing source."""
        target_info = self._set_element_info(error['input']['target'], 'target')
        message = f"{error.get('msg', 'Edge has no source')}.{target_info}"

        self.validator.add_result(
            severity=ValidationSeverity.ERROR,
            message=message,
            element_id=error['input']['id'],
            element_type='Edge',
            field_name='source'
        )

    def _set_element_info(self, element_id: str, role: str):
        """Get formatted information about an element for error messages."""
        if not self.diagram or not element_id:
            return

        # Check if it's a node
        if element_id in self.diagram.nodes:
            node = self.diagram.nodes[element_id]
            return f" {role.capitalize()} is a {node.shape.value} node, label is '{node.label}'"

        # Check if it's a select option (needs to search through nodes)
        for node in self.diagram.nodes.values():
            if node.options:
                for option in node.options:
                    if option.id == element_id:
                        return f" {role.capitalize()} is a select option, it's label is '{option.label}' "

        # Check if it's a group
        if element_id in self.diagram.groups:
            group = self.diagram.groups[element_id]
            element_count = len(group.contained_elements)
            return f" {role.capitalize()} is a group with {element_count} elements, label is '{group.label}'"

        return f" {role.capitalize()} ID exists but element not found in diagram"
