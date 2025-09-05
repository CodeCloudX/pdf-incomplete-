# tools/merge_tool.py
import os
import logging
from PyPDF2 import PdfMerger
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

logger = logging.getLogger(__name__)

def merge_pdfs(file_paths):
    """
    Merge multiple PDF files into one.
    file_paths: list of PDF file paths to merge
    """
    try:
        # Validate all files
        for file_path in file_paths:
            if not validate_file_size(file_path):
                return {
                    'status': 'error',
                    'output_files': [],
                    'message': f"File {os.path.basename(file_path)} exceeds size limit"
                }

        # Generate secure file name for output
        file_names = generate_file_names("merged_document.pdf", toolname='merge', ext='pdf')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        out_path = os.path.join(processed_folder, stored_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Merge PDFs
        merger = PdfMerger()
        for file_path in file_paths:
            merger.append(file_path)

        merger.write(out_path)
        merger.close()

        logger.info(f"Merged {len(file_paths)} PDFs into {out_path}")
        return {
            'status': 'success',
            'output_files': [{
                'display_name': display_name,
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f"Merged {len(file_paths)} PDFs successfully"
        }

    except Exception as e:
        logger.error(f"PDF merge failed: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Merge failed: {str(e)}"
        }
