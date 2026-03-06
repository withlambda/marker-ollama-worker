# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_pdf(filename, text):
    """
    Creates a simple PDF file with the given text.

    Args:
        filename (str): The path to the output PDF file.
        text (str): The text content to write to the PDF.
    """
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, text)
    c.save()
    print(f"Created {filename}")

def main():
    """
    Main function to generate sample PDF files for testing.
    """
    # Define the output directory as the input dir for the further marker-pdf
    # processing
    output_dir = os.environ['TEST_INPUT_DIR']

    # Create the directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    # Create sample PDF 1
    create_pdf(os.path.join(output_dir, "test1.pdf"), "This is a test PDF file number 1. It contains simple text for testing purposes.")

    # Create sample PDF 2
    create_pdf(os.path.join(output_dir, "test2.pdf"), "This is the second test PDF file. It is used to verify batch processing capabilities.")

if __name__ == "__main__":
    main()
