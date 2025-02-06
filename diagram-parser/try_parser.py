# Create a simple script try_parser.py

from questionnaire_parser.core.parser import DrawIoParser

# Create a small test diagram file
test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel>
    <!-- Your test diagram content -->
</mxGraphModel>"""

# Write it to a file
with open("test.xml", "w") as f:
    f.write(test_xml)

# Try parsing it
parser = DrawIoParser()
#diagram = parser.parse_file("test.xml")
diagram = parser.parse_file("/home/rafael/Documents/Business/MSF/diagrams_from_Job/dx_without_pictures.drawio")
print("Parsed diagram:", diagram)