# tools/pdf_to_jpg_tool.py
import os
import zipfile
import logging
import re
import shutil 
import fitz  # PyMuPDF
from flask import current_app
from PIL import Image
import io
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder, get_session_previews_folder
from utils.file_naming_utils import generate_file_names

# Import from generic_tools for preview generation and high quality image generation
from tools.generic_tools import generate_preview_thumbnails, generate_high_quality_images, PLACEHOLDER_FILENAME

# Set up logger
logger = logging.getLogger(__name__)

def pdf_to_jpg(file_path, pages=None, dpi=300, generate_previews=True):
    """Convert PDF pages to high quality JPG images and return as a ZIP"""
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
        file_names = generate_file_names(original_filename, toolname='jpg', ext='zip')
        display_name = file_names['display_name']
        stored_name = file_names['stored_name']

        # Get session-specific folders
        processed_folder = get_session_folder('processed')
        upload_folder = get_session_folder('uploads')
        out_path = os.path.join(processed_folder, stored_name)
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        os.makedirs(upload_folder, exist_ok=True)

        # Generate preview thumbnails using the existing function from generic_tools
        preview_files = []
        if generate_previews:
            try:
                preview_files = generate_preview_thumbnails(
                    file_path, 
                    preview_folder=get_session_previews_folder(),
                    max_pages=5,  # Generate previews for first 5 pages
                    dpi=100  # Lower DPI for previews
                )
            except Exception as e:
                logger.warning(f"Preview generation failed: {str(e)}")
                preview_files = []

        # Generate high quality images using the new function
        temp_image_dir = os.path.join(upload_folder, f"temp_jpg_{stored_name}")
        os.makedirs(temp_image_dir, exist_ok=True)
        
        # Convert pages to high quality images
        image_files = generate_high_quality_images(
            file_path, 
            temp_image_dir, 
            pages=pages, 
            dpi=dpi, 
            quality=95
        )

        if not image_files:
            return {
                'status': 'error',
                'output_files': [],
                'message': "No pages found for conversion or conversion failed"
            }

        # Create ZIP file with high quality images
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for img_path in image_files:
                zipf.write(img_path, os.path.basename(img_path))

        # Cleanup temporary images
        for img_path in image_files:
            if os.path.exists(img_path):
                os.remove(img_path)
        if os.path.exists(temp_image_dir):
            shutil.rmtree(temp_image_dir)

        logger.info(f"Successfully converted {file_path} to high quality JPG images: {out_path}")
        
        # Prepare response
        response = {
            'status': 'success',
            'output_files': [{
                'display_name': f"images_{display_name}.zip",
                'stored_name': stored_name,
                'output_path': out_path
            }],
            'message': f'PDF converted to {len(image_files)} high quality JPG images. DPI: {dpi}'
        }
        
        # Add previews to response if generated
        if generate_previews and preview_files:
            previews_folder = get_session_previews_folder()
            response['preview_files'] = [{
                'display_name': f"preview_{os.path.splitext(original_filename)[0]}_{i+1}.jpg",
                'stored_name': filename,
                'output_path': os.path.join(previews_folder, filename)
            } for i, filename in enumerate(preview_files) if filename != PLACEHOLDER_FILENAME]
        
        return response

    except Exception as e:
        logger.error(f"PDF to JPG conversion failed for {file_path}: {str(e)}")
        
        # Cleanup on error
        temp_image_dir = os.path.join(get_session_folder('uploads'), f"temp_jpg_{os.path.basename(file_path)}")
        if os.path.exists(temp_image_dir):
            for file in os.listdir(temp_image_dir):
                os.remove(os.path.join(temp_image_dir, file))
            shutil.rmtree(temp_image_dir)
            
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Conversion failed: {str(e)}"
        }
