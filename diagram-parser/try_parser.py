from questionnaire_parser.utils.debugging import debug_parsing

if __name__ == "__main__":
    # Replace with path to your test draw.io file
    xml_path = "diagram-parser/tests/test_data/valid_diagrams/dx_without_pictures.drawio"
    debug_parsing(xml_path)