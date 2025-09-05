# tools/pdf_to_text_tool.py
import os
import logging
import fitz  # PyMuPDF
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def pdf_to_text(file_path, pages=None, preserve_layout=True, include_page_numbers=True):
    """Extract text from PDF and save as .txt file - compatible with generic_tools.py"""
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
        file_names = generate_file_names(original_filename, toolname='text', ext='txt')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        doc = fitz.open(file_path)
        text_out = ""

        # Determine which pages to process
        if pages:
            # Convert to 0-based indexing and filter valid pages
            pages_to_process = [p-1 for p in pages if 0 <= p-1 < len(doc)]
            if not pages_to_process:
                doc.close()
                return {
                    'status': 'error',
                    'output_files': [],
                    'message': "No valid pages selected for text extraction"
                }
        else:
            pages_to_process = range(len(doc))

        # Extract text from selected pages
        for page_num in pages_to_process:
            try:
                page = doc[page_num]
                if include_page_numbers:
                    text_out += f"--- Page {page_num + 1} ---\n\n"
                
                if preserve_layout:
                    text_out += page.get_text("text") + "\n\n"  # "text" preserves layout better
                else:
                    text_out += page.get_text("words") + "\n\n"  # "words" might be less structured
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                continue

        doc.close()

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text_out)

        logger.info(f"Successfully extracted text from {file_path} to {out_path}")
        
        return {
            'status': 'success',
            'output_files': [{
                'display_name': f"text_{display_name}.txt",
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f'Text extracted from {len(pages_to_process)} pages successfully. Layout preserved: {preserve_layout}, Page numbers: {include_page_numbers}'
        }

    except Exception as e:
        logger.error(f"Text extraction failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Text extraction failed: {str(e)}"
        }
