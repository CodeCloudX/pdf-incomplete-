# tools/compress_tool.py
import os
import logging
import fitz  # PyMuPDF
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_processed_folder  # CHANGED
from utils.file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def compress_pdf(file_path, pages=None, compression_quality=0.5):
    """Compress PDF by downsampling images with optional page selection"""
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
        file_names = generate_file_names(original_filename, toolname='compress', ext='pdf')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific processed folder - CHANGED
        processed_folder = get_session_processed_folder()  # Using the proper function
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Open PDF for compression
        doc = fitz.open(file_path)
        
        # If specific pages are requested, filter them
        if pages:
            # Convert to 0-based indexing
            pages = [p-1 for p in pages if 0 <= p-1 < len(doc)]
            if not pages:
                doc.close()
                return {
                    'status': 'error',
                    'output_files': [],
                    'message': "No valid pages selected for compression"
                }
            
            # Create new document with selected pages
            new_doc = fitz.open()
            for page_num in pages:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            doc.close()
            doc = new_doc
        
        # Downsample embedded images
        for page in doc:
            images = page.get_images(full=True)
            for img in images:
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image["image"]

                    pix = fitz.Pixmap(img_bytes)

                    # Convert CMYK → RGB if needed
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    # Scale down based on quality
                    scaled = fitz.Pixmap(pix, compression_quality)

                    doc.update_image(xref, scaled)

                    pix = None
                    scaled = None
                except Exception as e:
                    logger.warning(f"Could not process image {xref}: {e}")
                    continue  # skip corrupt images

        # Save compressed PDF
        doc.save(out_path, deflate=True, garbage=4, clean=True)
        doc.close()
        
        logger.info(f"Successfully compressed {file_path} to {out_path}")
        
        return {
            'status': 'success',
            'output_files': [{
                'display_name': f"compressed_{display_name}.pdf",
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f'PDF compressed successfully. Quality: {compression_quality}'
        }

    except Exception as e:
        logger.error(f"Compression failed for {file_path}: {str(e)}")
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Compression failed: {str(e)}"
        }
