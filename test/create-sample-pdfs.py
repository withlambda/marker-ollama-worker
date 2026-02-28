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
