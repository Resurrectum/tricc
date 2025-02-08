parser = DrawIoParser()
try:
    diagram = parser.parse_file("my_diagram.drawio")
    # Diagram is now a valid Diagram instance
except XMLParsingError as e:
    print(f"Failed to parse XML: {e}")
except ValidationError as e:
    print(f"Invalid diagram structure: {e}")