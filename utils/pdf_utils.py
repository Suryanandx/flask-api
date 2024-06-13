import os
import logging
import subprocess
import tabula
import fitz
from PyPDF2 import PdfReader, PdfFileReader
from werkzeug.utils import secure_filename

# Function to process a PDF file and extract text
def process_pdf(file_path, pages):
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            text = ""
            for page_num in range(len(pdf_reader.pages)):                
                if pages == "all" or str(page_num) in pages:
                    text += pdf_reader.pages[page_num - 1].extract_text()
        return text
    except Exception as e:
        logging.error(f"Error processing PDF: {str(e)}")
        return None

def pdf_to_image(pdf_location, pages):
    try:
        print(pdf_location)
        images = []
        doc = fitz.open(pdf_location)
        for count, page in enumerate(pages):
           print(page)
           loaded_page = doc.load_page(int(page) - 1)  # number of page
           print("opend file")
           pix = loaded_page.get_pixmap()
           print("pix")
           output = f"{os.path.splitext(pdf_location)[0]}-{count}.jpg"
           print(output)
           pix.save(output)
           print("saved output")
           base64_image = encode_image( f"{os.path.splitext(pdf_location)[0]}-{count}.jpg")
           images.append(base64_image)
        return images
    except Exception as e:
        logging.error(f"Error processing PDF: {str(e)}")
        return None

def total_pages(pdf):
    with open(pdf, 'rb') as file:
        pdf_object = PdfFileReader(file)
        pages = ','.join([str(i) for i in range(pdf_object.getNumPages())])
    return pages

def extract_tables(pdf, pattern):
    try:
        cmd = f"pdfgrep -Pn '{pattern}' {pdf} | awk -F\":\" '$0~\":\"{{print $1}}' | tr '\n' ','"
        print(cmd)
        logging.info(cmd)
        pages = subprocess.check_output(cmd, shell=True).decode("utf-8")
        logging.info(f'count of pages {pages}')
        if not pages:
            logging.warning(f"No matching pages found in {pdf}")
            return

        tabula.convert_into(pdf, f"{os.path.splitext(pdf)[0]}.csv", output_format="csv", pages="39")
        # jsonoutput = tabula.read_pdf(pdf, output_format="json", pages="39")
        # print(jsonoutput)
        logging.info(f"Processed {pdf}")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        logging.error(f"Error processing {pdf}: {str(e)}")

# Function to process a PDF file and store it in the 'uploads' folder
def process_pdf_and_store(file):
    try:
        uploads_folder = os.path.join(os.getcwd(), "uploads")
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)

        filename = secure_filename(file.filename)
        file_path = os.path.join(uploads_folder, filename)
        file.save(file_path)

        text = process_pdf(file_path, "all")
        if text is not None:
            return filename
        else:
            os.remove(file_path)
            return None
    except Exception as e:
        logging.error(f"Error processing PDF and storing: {str(e)}")
        return None

