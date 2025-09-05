# tools/rotate_tool.py
import os
import logging
from PyPDF2 import PdfReader, PdfWriter
from flask import current_app
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

logger = logging.getLogger(__name__)

def rotate_pdf(file_path, pages=None, rotation_angles=None):
    """
    Rotate specified pages of a PDF.
    pages: list of 1-based page numbers to rotate (optional)
    rotation_angles: dict mapping 0-based page index (as string) to rotation angle in degrees
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
        file_names = generate_file_names(original_filename, toolname='rotate', ext='pdf')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        reader = PdfReader(file_path)
        writer = PdfWriter()

        total_pages = len(reader.pages)

        # If no pages specified, rotate all pages by 90 degrees default
        if not pages:
            pages_to_rotate = list(range(total_pages))
        else:
            pages_to_rotate = [p-1 for p in pages if 0 <= p-1 < total_pages]

        for i in range(total_pages):
            page = reader.pages[i]
            if i in pages_to_rotate:
                angle = 90  # default rotation
                if rotation_angles and str(i) in rotation_angles:
                    angle = rotation_angles[str(i)]
                page.rotate(angle)
            writer.add_page(page)

        with open(out_path, "wb") as f_out:
            writer.write(f_out)

        logger.info(f"Rotated pages in {file_path} saved to {out_path}")
        return {
            'status': 'success',
            'output_files': [{
                'display_name': f"rotated_{display_name}.pdf",
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f"Rotated {len(pages_to_rotate)} pages"
        }

    except Exception as e:
        logger.error(f"Rotate PDF failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Rotation failed: {str(e)}"
        }
