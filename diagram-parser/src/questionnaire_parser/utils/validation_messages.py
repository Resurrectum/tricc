from enum import Enum
from lxml import etree as ET
from pydantic_core import ErrorDetails


class EdgeValidationMessage(Enum):
    """Edge validation error messages.
    
    This enum represents all possible validation error messages for edges in our diagram.
    It includes both the message templates and the logic for formatting them.
    
    Each enum value is a message template that can include placeholders like {field_name}.
    These placeholders are filled in when the message is used to create the final error message.
    """
    NONE_ERROR_SOURCE = "The edge {edge_id} has no {field_name}. It's target is {target_id}."
    NONE_ERROR_TARGET = "The edge {edge_id} has no {field_name}. It's source is {source_id}."
    NONE_ERROR_BOTH = "The edge {edge_id} has neither source nor target."
    INVALID_GENERAL = "Invalid {field_name} in edge {edge_id}: {error_msg}."

    @classmethod
    def format_pydantic_error(cls, error_details: ErrorDetails, cell: ET.Element) -> str:
        """Format a Pydantic validation error into a user-friendly message.
        
        This method converts Pydantic's technical validation errors into clear,
        user-friendly messages using our predefined message templates. By being
        a class method, it has direct access to all our message templates and
        maintains the connection between messages and their formatting logic.

        Args:
            error_details: The error dictionary from Pydantic's ValidationError
            cell: The XML element representing the edge

        Returns:
            A formatted, user-friendly error message
        """
        error_type = error_details['type']
        field_name = '.'.join(str(loc) for loc in error_details['loc'])
        edge_id = cell.get('id')
        source_id = cell.get('source') # attempt to read source id from the edge
        target_id = cell.get('target') # attempt to read target id from the edge


        # Choose the appropriate message template based on the error type
        # if there is no source but there is a target:
        if error_type == 'string_type' and error_details.get('input') is None and not source_id and target_id:
            message_template = cls.NONE_ERROR_SOURCE.value
        # if there is no target but there is a source:
        elif error_type == 'string_type' and error_details.get('input') is None and source_id and not target_id:
            message_template = cls.NONE_ERROR_TARGET.value
        else:
            # For unhandled error types, use the general format
            message_template = cls.INVALID_GENERAL.value

        # Format the chosen template with the provided values
        return message_template.format(
            field_name=field_name,
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            error_msg=error_details.get('msg', '')
        )
