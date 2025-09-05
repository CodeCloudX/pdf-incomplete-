# tools/protect_pdf_tool.py
import os
import logging
from flask import current_app
from pikepdf import Pdf, Encryption, Permissions
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def protect_pdf(file_path, password=None, permissions_config=None):
    """Protect PDF with passwords and permissions - compatible with generic_tools.py"""
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
        file_names = generate_file_names(original_filename, toolname='protect', ext='pdf')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Default permissions if not provided or empty
        if permissions_config is None:
            permissions_config = {}

        # Convert string 'true'/'false' to actual booleans
        allow_printing = str(permissions_config.get('allow_printing', True)).lower() == 'true'
        allow_copying = str(permissions_config.get('allow_copying', True)).lower() == 'true'
        allow_modification = str(permissions_config.get('allow_modification', True)).lower() == 'true'

        logger.info(f"Permissions: printing={allow_printing}, copying={allow_copying}, modification={allow_modification}")

        # Open PDF
        pdf = Pdf.open(file_path)

        # Create permissions object with individual boolean parameters
        permissions = Permissions(
            accessibility=allow_copying,      # Allows content copying for accessibility
            extract=allow_copying,            # Allows content copying
            print_lowres=allow_printing,      # Allows low-resolution printing
            print_highres=allow_printing,     # Allows high-resolution printing
            modify_annotation=allow_modification,  # Allows annotation modification
            modify_other=allow_modification,  # Allows other modifications
        )

        # Apply encryption
        if password:
            encryption = Encryption(
                owner=password,
                user=password,
                allow=permissions
            )
        else:
            # If no password, still apply permissions
            encryption = Encryption(allow=permissions)

        pdf.save(out_path, encryption=encryption)
        pdf.close()

        logger.info(f"Successfully protected {file_path} -> {out_path}")
        
        return {
            'status': 'success',
            'output_files': [{
                'display_name': f"protected_{display_name}.pdf",
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f'PDF protected successfully. Printing: {allow_printing}, Copying: {allow_copying}, Modification: {allow_modification}'
        }

    except Exception as e:
        logger.error(f"PDF protection failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Error protecting PDF: {str(e)}"
        }
