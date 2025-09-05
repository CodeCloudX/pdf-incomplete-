# tools/pdf_to_word_tool.py
import os
import logging
from flask import current_app
from pdf2docx import Converter
import fitz  # PyMuPDF
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def pdf_to_word(file_path, pages=None):
    """Convert PDF to Word (.docx) preserving layout and images - compatible with generic_tools.py"""
    try:
        # Validate file size
        if not validate_file_size(file_path):
            return {
                'status': 'error',
                'output_files': [],
                'message': f"File {os.path.basename(file_path)} exceeds size limit"
            }

        # Get original filename for display purposes
        original_filename = os.path.basename(file_path)
        
        # Generate secure file names for output
        file_names = generate_file_names(original_filename, toolname='word', ext='docx')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Determine page range for conversion
        doc_pdf = fitz.open(file_path)
        
        pages_to_process_count = 0
        if pages:
            # Convert to 0-based indexing and filter valid pages
            pages_to_process_0_based = [p-1 for p in pages if 0 <= p-1 < len(doc_pdf)]
            if not pages_to_process_0_based:
                doc_pdf.close()
                return {
                    'status': 'error',
                    'output_files': [],
                    'message': "No valid pages selected for conversion"
                }
            start_page = min(pages_to_process_0_based)
            end_page = max(pages_to_process_0_based)  # pdf2docx uses inclusive end for 0-based
            pages_to_process_count = len(pages_to_process_0_based)
        else:
            start_page = 0
            end_page = len(doc_pdf) - 1  # pdf2docx uses inclusive end for 0-based
            pages_to_process_count = len(doc_pdf)
        
        doc_pdf.close()

        # Convert PDF → Word
        cv = Converter(file_path)
        cv.convert(out_path, start=start_page, end=end_page)
        cv.close()

        logger.info(f"Successfully converted {file_path} to Word: {out_path}")
        
        return {
            'status': 'success',
            'output_files': [{
                'display_name': f"word_{display_name}.docx",
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f'PDF converted to Word successfully. Pages: {pages_to_process_count}'
        }

    except Exception as e:
        logger.error(f"PDF to Word conversion failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Conversion failed: {str(e)}"
        }
