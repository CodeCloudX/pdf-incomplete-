# tools/unlock_pdf_tool.py
import os
import logging
from flask import current_app
from pikepdf import Pdf, PasswordError
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def unlock_pdf(file_path, password=None):
    """Unlock password-protected PDF and return unlocked version - compatible with generic_tools.py"""
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
        file_names = generate_file_names(original_filename, toolname='unlock', ext='pdf')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        try:
            # Try to open with password (if provided) or without password
            pdf = Pdf.open(file_path, password=password if password else None)

            # Save unlocked PDF
            pdf.save(out_path)
            pdf.close()

            logger.info(f"Successfully unlocked {file_path} -> {out_path}")
            
            return {
                'status': 'success',
                'output_files': [{
                    'display_name': f"unlocked_{display_name}.pdf",
                    'stored_name': stored_name,
                    'output_path': out_path
                }],
                'message': 'PDF unlocked successfully'
            }

        except PasswordError:
            logger.warning(f"Failed to unlock {file_path}: Incorrect password")
            return {
                'status': 'error',
                'output_files': [],
                'message': "Incorrect password. Could not unlock the PDF."
            }

    except Exception as e:
        logger.error(f"PDF unlock failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Error unlocking PDF: {str(e)}"
        }
