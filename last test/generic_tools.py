# tools/generic_tools.py
import os
import logging
import platform
import traceback
import tempfile
import shutil
from typing import Dict, List, Optional, Union, Callable, Any, Tuple
from flask import current_app
from PyPDF2 import PdfReader
import fitz
import zipfile
import time
from functools import wraps, lru_cache
from datetime import datetime
import uuid

# Import from utils
from utils.file_utils import validate_file_size, validate_total_file_size, cleanup_temp_files
from utils.file_manager import get_session_folder
from utils.file_naming_utils import generate_file_names

# ------------------- Configuration -------------------
class ToolConfig:
    ALLOWED_EXTENSIONS = {'pdf'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    DEFAULT_PREVIEW_PAGES = 3
    MAX_CONCURRENT_PROCESSES = 4
    REQUEST_TIMEOUT = 300  # 5 minutes
    THUMBNAIL_DPI = 100  # DPI for thumbnail generation
    MAX_THUMBNAILS_PER_FILE = 50  # Limit to prevent memory issues
    HIGH_QUALITY_DPI = 300  # High quality DPI for conversions

# ------------------- Logging Setup -------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ------------------- Utility Functions -------------------
def rate_limited(max_per_minute: int):
    """Decorator to limit function execution rate"""
    min_interval = 60.0 / max_per_minute
    def decorator(func):
        last_time_called = 0.0
        @wraps(func)
        def rate_limited_function(*args, **kwargs):
            nonlocal last_time_called
            elapsed = time.time() - last_time_called
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            last_time_called = time.time()
            return func(*args, **kwargs)
        return rate_limited_function
    return decorator

def sanitize_filename(filename: str) -> str:
    """Prevent directory traversal attacks"""
    return os.path.basename(filename)

def validate_page_selections(page_selection: Dict, max_pages: int) -> bool:
    """Validate that page selections are within bounds"""
    for filename, pages in page_selection.items():
        if any(page < 1 or page > max_pages for page in pages):
            return False
    return True

# ------------------- Check if PDF is encrypted -------------------
def is_pdf_encrypted(pdf_path: str) -> bool:
    """Check if a PDF file is encrypted"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            return reader.is_encrypted
    except Exception as e:
        logger.error(f"Error checking if PDF is encrypted: {e}")
        return False

# Define the placeholder filename
PLACEHOLDER_FILENAME = "no_preview_available.jpg"

# ------------------- Generate Preview Thumbnails -------------------
def generate_preview_thumbnails(pdf_path: str, preview_folder: Optional[str] = None,
                               max_pages: Optional[int] = None, dpi: int = 100,
                               password: Optional[str] = None,
                               skip_if_encrypted: bool = False) -> List[str]:
    """
    Generates preview thumbnails for PDF pages using PyMuPDF.
    If max_pages is None, generates thumbnails for ALL pages.
    If max_pages is specified, generates only that many thumbnails.
    """
    if preview_folder is None:
        preview_folder = get_session_folder(current_app.config.get('PREVIEWS_FOLDER', 'previews'))

    os.makedirs(preview_folder, exist_ok=True)
    thumbnails = []

    try:
        # Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Determine how many pages to process
        if max_pages is None:
            pages_to_process = total_pages  # Process all pages for preview
        else:
            pages_to_process = min(total_pages, max_pages)  # Use specified max_pages

        # Apply the global limit
        pages_to_process = min(pages_to_process, ToolConfig.MAX_THUMBNAILS_PER_FILE)

        # Check for encrypted files and skip preview if requested
        if skip_if_encrypted and doc.is_encrypted:
            logger.info(f"Skipping preview generation for encrypted PDF: {pdf_path}")
            doc.close()
            return [PLACEHOLDER_FILENAME] * pages_to_process if pages_to_process > 0 else []

        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # Process pages
        for page_num in range(pages_to_process):
            try:
                page = doc.load_page(page_num)
                
                # Calculate zoom factor based on DPI (approximate conversion)
                zoom = dpi / 72  # 72 is the default PDF DPI
                mat = fitz.Matrix(zoom, zoom)
                
                # Create pixmap
                pix = page.get_pixmap(matrix=mat)
                
                # Generate secure filename
                file_names = generate_file_names(f"{base_name}_page{page_num+1}.jpg", toolname='preview')
                thumb_filename = file_names['stored_name']
                thumb_path = os.path.join(preview_folder, thumb_filename)
                
                # Save as JPEG
                pix.save(thumb_path, output="jpeg", jpg_quality=85)
                thumbnails.append(thumb_filename)
                
            except Exception as e:
                logger.warning(f"Failed to process page {page_num + 1}: {e}")
                continue

        doc.close()
        return thumbnails

    except Exception as e:
        logger.error(f"Thumbnail generation failed for {pdf_path}: {e}")
        try:
            doc.close()
        except:
            pass
        # If thumbnail generation fails, return placeholders
        return [PLACEHOLDER_FILENAME] * pages_to_process if pages_to_process > 0 else []

# ------------------- Generate High Quality Images -------------------
def generate_high_quality_images(pdf_path: str, output_folder: str, pages: List[int] = None, 
                                dpi: int = 300, quality: int = 95) -> List[str]:
    """
    Generate high quality images from PDF using PyMuPDF.
    Returns list of generated image file paths.
    """
    os.makedirs(output_folder, exist_ok=True)
    images = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Determine which pages to process
        if pages:
            page_indices = [p-1 for p in pages if 1 <= p <= total_pages]
        else:
            page_indices = range(total_pages)
        
        if not page_indices:
            doc.close()
            return []
        
        # Calculate zoom factor for high DPI
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        for page_num in page_indices:
            try:
                page = doc.load_page(page_num)
                
                # Create high quality pixmap
                pix = page.getpixmap(matrix=mat)
                
                # Generate secure filename
                file_names = generate_file_names(f"{base_name}_page{page_num+1}.jpg", toolname='jpg')
                img_filename = file_names['stored_name']
                img_path = os.path.join(output_folder, img_filename)
                
                # Save as high quality JPEG
                pix.save(img_path, output="jpeg", jpg_quality=quality)
                images.append(img_path)
                
            except Exception as e:
                logger.warning(f"Failed to process page {page_num + 1} for high quality image: {e}")
                continue
        
        doc.close()
        return images
        
    except Exception as e:
        logger.error(f"High quality image generation failed for {pdf_path}: {e}")
        try:
            doc.close()
        except:
            pass
        return []
    
# ------------------- Get PDF Page Count -------------------
@lru_cache(maxsize=100)
def get_pdf_page_count(filepath: str) -> int:
    """Get PDF page count with caching, handles encrypted files"""
    try:
        # Use PyPDF2 to get page count
        with open(filepath, 'rb') as f:
            reader = PdfReader(f)
            if reader.is_encrypted:
                try:
                    # Attempt to get page count for encrypted files
                    return len(reader.pages)
                except Exception:
                    logger.warning(f"Could not get page count for encrypted PDF {filepath} using PyPDF2.")
                    return 0  # Cannot determine page count for encrypted file without password
            else:
                return len(reader.pages)
    except Exception as e:
        logger.error(f"Failed to get page count for {filepath} using PyPDF2: {e}")
        return 0

# ------------------- Helper Function: Create ZIP -------------------
def create_zip_from_files(file_list: List[str], zip_prefix: str = "processed_files") -> str:
    """Create a ZIP archive from multiple files with a unique name."""
    processed_folder = get_session_folder(current_app.config.get('PROCESSED_FOLDER', 'processed'))
    os.makedirs(processed_folder, exist_ok=True)

    # Generate unique filename using centralized function
    file_names = generate_file_names(f"{zip_prefix}.zip", toolname='zip')
    zip_name = file_names['stored_name']
    zip_path = os.path.join(processed_folder, zip_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in file_list:
            if os.path.exists(file_path):
                zipf.write(file_path, arcname=os.path.basename(file_path))

    return zip_path

# ------------------- Allowed Tools -------------------
def _get_tool_function(tool_id: str):
    """Dynamically import tool function to avoid circular imports"""
    try:
        if tool_id == "split":
            from tools.split_tool import split_pdf
            return split_pdf
        elif tool_id == "merge":
            from tools.merge_tool import merge_pdfs
            return merge_pdfs
        elif tool_id == "rotate":
            from tools.rotate_tool import rotate_pdf
            return rotate_pdf
        elif tool_id == "compress":
            from tools.compress_tool import compress_pdf
            return compress_pdf
        elif tool_id == "pdf-to-word":
            from tools.pdf_to_word_tool import pdf_to_word
            return pdf_to_word
        elif tool_id == "pdf-to-excel":
            from tools.pdf_to_excel_tool import pdf_to_excel
            return pdf_to_excel
        elif tool_id == "pdf-to-ppt":
            from tools.pdf_to_ppt_tool import pdf_to_ppt
            return pdf_to_ppt
        elif tool_id == "pdf-to-jpg":
            from tools.pdf_to_jpg_tool import pdf_to_jpg
            return pdf_to_jpg
        elif tool_id == "pdf-to-text":
            from tools.pdf_to_text_tool import pdf_to_text
            return pdf_to_text
        elif tool_id == "ocr":
            from tools.ocr_tool import ocr_pdf
            return ocr_pdf
        elif tool_id == "unlock":
            from tools.unlock_pdf_tool import unlock_pdf
            return unlock_pdf
        elif tool_id == "protect":
            from tools.protect_pdf_tool import protect_pdf
            return protect_pdf
        else:
            return None
    except ImportError as e:
        logger.error(f"Failed to import tool {tool_id}: {e}")
        return None

# ------------------- Type Conversion Helper -------------------
def _convert_option_type(value: Any, target_type: type, default: Any = None) -> Any:
    """Converts a value to a target type, handling common string conversions."""
    if value is None:
        return default
    if target_type is bool:
        return str(value).lower() in ['true', 'on', '1', 'yes']
    if target_type is int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    if target_type is float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    return target_type(value)

# ------------------- Execute Tool Function -------------------
@rate_limited(30)  # Limit to 30 calls per minute
def execute_tool(tool_id: str, file_paths: List[str], page_selections: Optional[Dict] = None, 
                password: Optional[str] = None, tool_options: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute the specified tool with the given files and options."""
    logger.info(f"Executing tool {tool_id} with {len(file_paths)} files")
    logger.info(f"Tool options received: {tool_options}")
    logger.info(f"Page selections received: {page_selections}")

    # Initialize result with a default error response
    result = {
        'status': 'error',
        'output_files': [],
        'message': 'Tool execution failed'
    }
    
    # Validate total file size
    is_valid_size, size_error = validate_total_file_size(file_paths, max_total_size_mb=10)
    if not is_valid_size:
        return {
            'status': 'error',
            'output_files': [],
            'message': size_error
        }
    
    tool_func = _get_tool_function(tool_id)
    if tool_func is None:
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Unknown tool: {tool_id}"
        }
    
    if not file_paths:
        return {
            'status': 'error',
            'output_files': [],
            'message': "No files provided"
        }
    
    # Validate individual file sizes
    for file_path in file_paths:
        if not validate_file_size(file_path):
            return {
                'status': 'error',
                'output_files': [],
                'message': f"File {os.path.basename(file_path)} exceeds size limit"
            }
    
    processed_files = []
    try:
        # --- Merge tool requires 2+ files ---
        if tool_id == "merge":
            if len(file_paths) < 2:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "Merge requires at least 2 PDF files"
                }
            
            # Extract file order from tool_options
            file_order = tool_options.get('file_order', []) if tool_options else []
            if file_order:
                # Reorder files based on the specified order
                ordered_files = []
                for filename in file_order:
                    for file_path in file_paths:
                        if os.path.basename(file_path) == filename:
                            ordered_files.append(file_path)
                            break
                # Add any files not in the order list
                for file_path in file_paths:
                    if file_path not in ordered_files:
                        ordered_files.append(file_path)
                file_paths = ordered_files
            
            result = tool_func(file_paths)

        # --- Unlock / Protect: single-file only ---
        elif tool_id in ["unlock", "protect"]:
            if len(file_paths) != 1:
                return {
                    "status": "error",
                    'output_files': [],
                    "message": f"{tool_id.capitalize()} tool only supports single file"
                }
            
            # Extract password from tool_options
            tool_password = tool_options.get('password', password) if tool_options else password
            
            if tool_id == "unlock":
                result = tool_func(file_paths[0], tool_password)
            elif tool_id == "protect":
                # Extract permissions from tool_options
                permissions_config = {
                    'allow_printing': _convert_option_type(tool_options.get('allow_printing'), bool, True) if tool_options else True,
                    'allow_copying': _convert_option_type(tool_options.get('allow_copying'), bool, True) if tool_options else True,
                    'allow_modification': _convert_option_type(tool_options.get('allow_modification'), bool, True) if tool_options else True,
                }
                result = tool_func(file_paths[0], tool_password, permissions_config)

        # --- Split tool ---
        elif tool_id == "split":
            all_split_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Pass tool_options directly to split_pdf
                result = tool_func(file_path, pages, tool_options)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_split_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_split_files.append(output_file)
            
            if all_split_files:
                zip_file = create_zip_from_files(all_split_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Split {len(file_paths)} files into {len(all_split_files)} parts"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully split"
                }

        # --- Rotate tool ---
        elif tool_id == "rotate":
            all_rotated_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
        
                # Extract rotation options
                rotation_angle = _convert_option_type(tool_options.get('rotation_angle'), int, 90) if tool_options else 90
        
                # Create a rotation angle for each selected page if pages are specified
                rotation_angles_for_tool = None
                if pages:
                    rotation_angles_for_tool = {str(p-1): rotation_angle for p in pages}
        
                result = tool_func(file_path, pages=pages, rotation_angles=rotation_angles_for_tool)
        
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_rotated_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_rotated_files.append(output_file)
    
            if all_rotated_files:
                zip_file = create_zip_from_files(all_rotated_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Rotated {len(file_paths)} files"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully rotated"
                }
    
        # --- Compress tool ---
        elif tool_id == "compress":
            all_compressed_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Extract compression quality
                compression_quality = _convert_option_type(tool_options.get('compression_quality'), float, 0.5) if tool_options else 0.5
                
                result = tool_func(file_path, pages, compression_quality)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_compressed_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_compressed_files.append(output_file)
            
            if all_compressed_files:
                zip_file = create_zip_from_files(all_compressed_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Compressed {len(file_paths)} files"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully compressed"
                }

        # --- PDF to Word tool ---
        elif tool_id == "pdf-to-word":
            all_converted_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                result = tool_func(file_path, pages)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_converted_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_converted_files.append(output_file)
            
            if all_converted_files:
                zip_file = create_zip_from_files(all_converted_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Converted {len(file_paths)} PDFs to Word documents"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully converted to Word"
                }

        # --- PDF to Excel tool ---
        elif tool_id == "pdf-to-excel":
            all_converted_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Extract conversion options
                table_detection = tool_options.get('table_detection', 'auto') if tool_options else 'auto'
                excel_format = tool_options.get('excel_format', 'multi') if tool_options else 'multi'
                
                result = tool_func(file_path, pages, table_detection, excel_format)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_converted_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_converted_files.append(output_file)
            
            if all_converted_files:
                zip_file = create_zip_from_files(all_converted_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Converted {len(file_paths)} PDFs to Excel spreadsheets"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully converted to Excel"
                }

        # --- PDF to PowerPoint tool ---
        elif tool_id == "pdf-to-ppt":
            all_converted_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Extract conversion options
                slide_width = _convert_option_type(tool_options.get('slide_width'), float, 10.0) if tool_options else 10.0
                slide_height = _convert_option_type(tool_options.get('slide_height'), float, 7.5) if tool_options else 7.5
                
                result = tool_func(file_path, pages, slide_width, slide_height)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_converted_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_converted_files.append(output_file)
            
            if all_converted_files:
                zip_file = create_zip_from_files(all_converted_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Converted {len(file_paths)} PDFs to PowerPoint presentations"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully converted to PowerPoint"
                }

        # --- PDF to JPG tool ---
        elif tool_id == "pdf-to-jpg":
            all_converted_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Extract conversion options
                dpi_resolution = _convert_option_type(tool_options.get('dpi_resolution'), int, ToolConfig.HIGH_QUALITY_DPI) if tool_options else ToolConfig.HIGH_QUALITY_DPI
                
                result = tool_func(file_path, pages, dpi_resolution)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_converted_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_converted_files.append(output_file)
            
            if all_converted_files:
                zip_file = create_zip_from_files(all_converted_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Converted {len(file_paths)} PDFs to JPG images"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully converted to JPG"
                }

        # --- PDF to Text tool ---
        elif tool_id == "pdf-to-text":
            all_converted_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                result = tool_func(file_path, pages)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_converted_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_converted_files.append(output_file)
            
            if all_converted_files:
                zip_file = create_zip_from_files(all_converted_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Converted {len(file_paths)} PDFs to text files"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully converted to text"
                }

        # --- OCR tool ---
        elif tool_id == "ocr":
            all_converted_files = []
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Extract conversion options
                ocr_language = tool_options.get('ocr_language', 'eng') if tool_options else 'eng'
                ocr_output = tool_options.get('ocr_output', 'txt') if tool_options else 'txt'
                
                result = tool_func(file_path, pages, ocr_language, ocr_output)
                
                if isinstance(result, dict) and "output_files" in result:
                    # Extract actual file paths from the result dictionaries
                    for output_file in result["output_files"]:
                        if isinstance(output_file, dict) and "output_path" in output_file:
                            all_converted_files.append(output_file["output_path"])
                        elif isinstance(output_file, str):
                            all_converted_files.append(output_file)
            
            if all_converted_files:
                zip_file = create_zip_from_files(all_converted_files)
                return {
                    "status": "success",
                    "output_files": [zip_file],
                    "message": f"Processed {len(file_paths)} PDFs with OCR"
                }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully processed with OCR"
                }

        # --- Default case for other tools ---
        else:
            # Process each file individually
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                pages = page_selections.get(filename, []) if page_selections else []
                
                # Validate page selections
                max_pages = get_pdf_page_count(file_path)
                if pages and not validate_page_selections({filename: pages}, max_pages):
                    return {
                        "status": "error",
                        "output_files": [],
                        "message": f"Invalid page selection for {filename}"
                    }
                
                try:
                    # Call the tool function with pages if specified
                    if pages:
                        res = tool_func(file_path, pages)
                    else:
                        res = tool_func(file_path)
                    
                    if isinstance(res, dict) and "output_files" in res:
                        # Extract actual file paths from the result dictionaries
                        for output_file in res["output_files"]:
                            if isinstance(output_file, dict) and "output_path" in output_file:
                                processed_files.append(output_file["output_path"])
                            elif isinstance(output_file, str):
                                processed_files.append(output_file)
                    elif isinstance(res, str):
                        processed_files.append(res)
                    elif isinstance(res, list):
                        processed_files.extend(res)
                        
                except Exception as e:
                    logger.error(f"Error processing {file_path} with tool {tool_id}: {e}")
                    # Continue processing other files
                    continue
            
            if processed_files:
                # Create ZIP if multiple files were processed
                if len(processed_files) > 1:
                    zip_file = create_zip_from_files(processed_files)
                    return {
                        "status": "success",
                        "output_files": [zip_file],
                        "message": f"Processed {len(processed_files)} files from {len(file_paths)} inputs"
                    }
                else:
                    return {
                        "status": "success",
                        "output_files": processed_files,
                        "message": f"Successfully processed file"
                    }
            else:
                return {
                    "status": "error",
                    "output_files": [],
                    "message": "No files were successfully processed"
                }

        # Ensure the result has the expected format
        if isinstance(result, dict):
            if 'status' in result and 'output_files' in result:
                return result
            if 'output_files' in result:
                return {
                    'status': 'success',
                    'output_files': result.get('output_files', []),
                    'message': result.get('message', 'Processing complete')
                }

        if isinstance(result, list):
            return {
                'status': 'success',
                'output_files': result,
                'message': f'Successfully processed {len(result)} files'
            }

        return {
            'status': 'success',
            'output_files': [],
            'message': 'Processing completed but no files were generated'
        }

    except Exception as e:
        logger.error(f"Error in execute_tool for {tool_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'output_files': [],
            'message': f"Error processing files: {str(e)}"
        }
    finally:
        # Only clean up files that are in the UPLOAD_FOLDER
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        upload_folder_abs = os.path.abspath(upload_folder)
        
        files_to_cleanup = []
        for file_path in file_paths:
            file_path_abs = os.path.abspath(file_path)
            if file_path_abs.startswith(upload_folder_abs):
                files_to_cleanup.append(file_path)
        
        cleanup_temp_files(files_to_cleanup)

# ------------------- Helper Functions -------------------
def validate_pdf_password(pdf_path: str, password: str) -> bool:
    """Validate PDF password"""
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            if reader.is_encrypted:
                result = reader.decrypt(password)
                return result == 1
            else:
                return True
    except Exception:
        return False

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ToolConfig.ALLOWED_EXTENSIONS

# ------------------- Health Check -------------------
def health_check() -> Dict[str, Any]:
    """System health check"""
    import psutil
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }
