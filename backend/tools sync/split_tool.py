# tools/split_tool.py
import os
import json
import zipfile
import logging
import tempfile
import re
from flask import current_app
from PyPDF2 import PdfReader, PdfWriter
from utils.file_utils import validate_file_size
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def parse_page_ranges(page_ranges_str, total_pages):
    """
    Parse page range string like "1-3,5-7,9" into list of page numbers
    """
    pages = set()
    
    if not page_ranges_str:
        return list(range(1, total_pages + 1))
    
    # Split by commas
    ranges = page_ranges_str.split(',')
    
    for range_str in ranges:
        range_str = range_str.strip()
        if not range_str:
            continue
            
        # Handle single page
        if '-' not in range_str:
            try:
                page = int(range_str)
                if 1 <= page <= total_pages:
                    pages.add(page)
            except ValueError:
                continue
        # Handle page range
        else:
            try:
                start, end = range_str.split('-', 1)
                start = int(start.strip())
                end = int(end.strip())
                
                # Ensure valid range
                if start < 1:
                    start = 1
                if end > total_pages:
                    end = total_pages
                if start <= end:
                    pages.update(range(start, end + 1))
            except ValueError:
                continue
    
    return sorted(pages)

def split_pdf(file_path, pages=None, tool_options=None):
    """
    Split PDF into individual pages or ZIP archive - compatible with generic_tools.py
    file_path: path to the uploaded PDF
    pages: list of selected page numbers (1-indexed), optional
    tool_options: dict containing additional options like page_ranges, optional
    Returns dict: {"status": ..., "output_files": [...], "message": ...}
    """
    try:
        # Extract page_ranges and split_option from tool_options if provided
        page_ranges_str = tool_options.get('page_ranges', '') if tool_options else ''
        split_option = tool_options.get('split_option', 'all') if tool_options else 'all'
        
        logger.info(f"Starting split_pdf for: {file_path}, pages: {pages}, page_ranges_str: {page_ranges_str}, split_option: {split_option}")
        
        # Validate file size
        if not validate_file_size(file_path):
            logger.warning(f"File too large: {file_path}")
            return {
                'status': 'error',
                'output_files': [],
                'message': f"File {os.path.basename(file_path)} exceeds size limit"
            }

        # Get original filename for display purposes
        original_filename = os.path.basename(file_path)
        
        # Get session-specific processed folder
        processed_folder = get_session_folder('processed')
        
        # Ensure output directory exists
        os.makedirs(processed_folder, exist_ok=True)

        pdf = PdfReader(file_path)
        total_pages = len(pdf.pages)
        logger.info(f"PDF has {total_pages} pages")
        
        # Determine which pages to split based on priority:
        # 1. Explicit page_ranges_str from tool_options
        # 2. 'pages' list from page_selections
        # 3. All pages if neither is specified
        if page_ranges_str:
            pages_to_split_1_based = parse_page_ranges(page_ranges_str, total_pages)
            pages_to_split_0_based = [p-1 for p in pages_to_split_1_based]  # Convert to 0-based
        elif pages:
            pages_to_split_0_based = [p-1 for p in pages if 1 <= p <= total_pages]
        else:
            pages_to_split_0_based = list(range(total_pages))
        
        if not pages_to_split_0_based:
            logger.warning("No valid pages selected for splitting")
            return {
                'status': 'error',
                'output_files': [],
                'message': "No valid pages selected for splitting"
            }
        
        logger.info(f"Pages to split (0-based): {pages_to_split_0_based}")
        
        processed_files = []

        try:
            if split_option == 'all' or len(pages_to_split_0_based) > 1:
                # Create ZIP for multiple pages or if 'all' option is selected
                file_names = generate_file_names(original_filename, toolname='split', ext='zip')
                stored_name = file_names['stored_name']
                zip_path = os.path.join(processed_folder, stored_name)
                logger.info(f"Creating ZIP: {zip_path}")
                
                # Create temporary directory for individual pages
                with tempfile.TemporaryDirectory() as temp_dir:
                    logger.info(f"Using temp directory: {temp_dir}")
                    
                    # Create individual PDF pages first
                    page_files = []
                    for page_num_0_based in pages_to_split_0_based:
                        writer = PdfWriter()
                        writer.add_page(pdf.pages[page_num_0_based])
                        
                        # Generate secure name for individual page
                        page_file_names = generate_file_names(f"page_{page_num_0_based+1}_{original_filename}", toolname='split_page', ext='pdf')
                        page_filename = page_file_names['stored_name']
                        page_path = os.path.join(temp_dir, page_filename)
                        
                        logger.info(f"Creating page {page_num_0_based+1}: {page_path}")
                        with open(page_path, "wb") as f:
                            writer.write(f)
                        
                        # Verify page was created
                        if os.path.exists(page_path):
                            logger.info(f"Page created successfully: {page_path} ({os.path.getsize(page_path)} bytes)")
                            page_files.append(page_path)
                        else:
                            logger.error(f"Failed to create page: {page_path}")
                    
                    # Create ZIP with all pages
                    logger.info(f"Creating ZIP with {len(page_files)} pages")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for page_path in page_files:
                            zipf.write(page_path, os.path.basename(page_path))
                    
                    logger.info(f"ZIP created: {zip_path} ({os.path.getsize(zip_path)} bytes)")
                
                processed_files.append(zip_path)
                
            elif split_option == 'single' and len(pages_to_split_0_based) == 1:
                # Single page output
                page_num_0_based = pages_to_split_0_based[0]
                writer = PdfWriter()
                writer.add_page(pdf.pages[page_num_0_based])
                
                # Generate secure file name for single page
                file_names = generate_file_names(f"page_{page_num_0_based+1}_{original_filename}", toolname='split', ext='pdf')
                display_name = file_names['display_name']
                stored_name = file_names['stored_name']
                output_path = os.path.join(processed_folder, stored_name)
                logger.info(f"Creating single page: {output_path}")
                
                with open(output_path, "wb") as f:
                    writer.write(f)
                
                # Verify file was created
                if os.path.exists(output_path):
                    logger.info(f"Single page created: {output_path} ({os.path.getsize(output_path)} bytes)")
                    processed_files.append(output_path)
                else:
                    logger.error(f"Failed to create single page: {output_path}")
            else:
                logger.warning(f"Split option '{split_option}' not supported for current page selection or number of pages.")
                return {
                    'status': 'error',
                    'output_files': [],
                    'message': f"Split option '{split_option}' not supported for current page selection or number of pages."
                }

            logger.info(f"Successfully created {len(processed_files)} output file(s)")
            
            # Verify files actually exist
            for output_file in processed_files:
                if not os.path.exists(output_file):
                    logger.error(f"Output file does not exist: {output_file}")
                    return {
                        'status': 'error',
                        'output_files': [],
                        'message': f"Failed to create output file: {os.path.basename(output_file)}"
                    }
                else:
                    logger.info(f"Output file verified: {output_file} ({os.path.getsize(output_file)} bytes)")
            
            return {
                'status': 'success', 
                'output_files': [{
                    'display_name': f"split_{original_filename}",
                    'stored_name': os.path.basename(output_file),
                    'output_path': output_file
                } for output_file in processed_files],
                'message': f"Successfully split {len(pages_to_split_0_based)} page(s)"
            }

        except Exception as e:
            logger.error(f"Error during PDF splitting: {str(e)}", exc_info=True)
            # Cleanup any partially created files
            for output_file in processed_files:
                if os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                        logger.info(f"Cleaned up partial file: {output_file}")
                    except Exception as cleanup_error:
                        logger.error(f"Failed to cleanup {output_file}: {cleanup_error}")
            raise

    except Exception as e:
        logger.error(f"PDF split failed for {file_path}: {str(e)}", exc_info=True)
        return {
            'status': 'error', 
            'output_files': [], 
            'message': f"Split failed: {str(e)}"
        }
