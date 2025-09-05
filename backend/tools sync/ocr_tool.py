# tools/ocr_tool.py
import os
import logging
from flask import current_app
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

logger = logging.getLogger(__name__)

def ocr_pdf(file_path, pages=None, language='eng', output_type='txt'):
    """
    Perform OCR on PDF pages and output text or searchable PDF.
    pages: list of 1-based page numbers to process (optional)
    language: OCR language code (default 'eng')
    output_type: 'txt' or 'pdf' (default 'txt')
    """
    try:
        if not validate_file_size(file_path):
            return {
                'status': 'error',
                'output_files': [],
                'message': f"File {os.path.basename(file_path)} exceeds size limit"
            }

        # Get original filename for display purposes
        original_filename = os.path.basename(file_path)
        
        # Generate secure file names for output
        if output_type == 'txt':
            ext = 'txt'
        elif output_type == 'pdf':
            ext = 'pdf'
        else:
            return {
                'status': 'error',
                'output_files': [],
                'message': f"Unsupported OCR output type: {output_type}"
            }
            
        file_names = generate_file_names(original_filename, toolname='ocr', ext=ext)
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        doc = fitz.open(file_path)
        total_pages = len(doc)

        # Determine pages to process (0-based)
        if pages:
            pages_to_process = [p-1 for p in pages if 0 <= p-1 < total_pages]
            if not pages_to_process:
                doc.close()
                return {
                    'status': 'error',
                    'output_files': [],
                    'message': "No valid pages selected for OCR"
                }
        else:
            pages_to_process = list(range(total_pages))

        if output_type == 'txt':
            text_output = ""
            for page_num in pages_to_process:
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img, lang=language)
                text_output += f"--- Page {page_num + 1} ---\n{text}\n\n"

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text_output)

            doc.close()
            logger.info(f"OCR text extracted for {file_path} to {out_path}")
            return {
                'status': 'success',
                'output_files': [{
                    'display_name': f"ocr_{display_name}.txt",
                    'stored_name': stored_name,
                    'output_path': out_path
                }],
                'message': f"OCR text extracted from {len(pages_to_process)} pages"
            }

        elif output_type == 'pdf':
            # Create a new PDF with OCR text layer
            new_doc = fitz.open()
            for page_num in pages_to_process:
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_pdf_or_hocr(img, lang=language, extension='pdf')
                # Insert OCR page as PDF page
                ocr_page = fitz.open("pdf", text)
                new_doc.insert_pdf(ocr_page)
            
            new_doc.save(out_path)
            new_doc.close()
            doc.close()
            logger.info(f"OCR PDF created for {file_path} at {out_path}")
            return {
                'status': 'success',
                'output_files': [{
                    'display_name': f"ocr_{display_name}.pdf",
                    'stored_name': stored_name,
                    'output_path': out_path
                }],
                'message': f"OCR PDF created from {len(pages_to_process)} pages"
            }
        else:
            doc.close()
            return {
                'status': 'error',
                'output_files': [],
                'message': f"Unsupported OCR output type: {output_type}"
            }

    except Exception as e:
        logger.error(f"OCR failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"OCR failed: {str(e)}"
        }
