import logging
from pathlib import Path
from questionnaire_parser.utils.debugging import debug_parsing
from questionnaire_parser.core.parser import ValidationLevel


if __name__ == "__main__":
    # Replace with path to your test draw.io file
    xml_path = Path("diagram-parser/tests/test_data/valid_diagrams/dx_without_pictures.drawio")
    debug_parsing(xml_path, validation_level = ValidationLevel.LENIENT, logging_level=logging.DEBUG)