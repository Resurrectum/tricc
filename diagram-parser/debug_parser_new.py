import logging
from questionnaire_parser.core.parser import DrawIoParser
from questionnaire_parser.exceptions.parsing import XMLParsingError

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    parser = DrawIoParser()
    try:
        # Add the path to your XML file
        diagram = parser.parse_file("/home/rafael/repos/TRICC/diagram-parser/examples/dx_without_pictures.drawio")
    except XMLParsingError as e:
        logger.exception("Failed to parse diagram")
        raise  # This will re-raise with the full traceback
    except Exception as e:
        logger.exception("Unexpected error")
        raise  # This will re-raise with the full traceback

if __name__ == "__main__":
    main()