# utils/file_utils.py
import os
import uuid
import logging
from werkzeug.utils import secure_filename
from flask import current_app, session
from typing import List, Tuple
from .file_manager import get_session_folder
from .file_naming_utils import generate_file_names

# Set up logger
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.
    Uses ALLOWED_EXTENSIONS from app config.
    """
    allowed_extensions = getattr(current_app.config, "ALLOWED_EXTENSIONS", {'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_file(file):
    """
    Validate file type and size based on config.
    Returns (True, None) if valid, else (False, error_message)
    """
    if not file or file.filename == '':
        return False, "No file selected."

    if not allowed_file(file.filename):
        return False, "Invalid file type. Only PDFs allowed."

    file.seek(0, os.SEEK_END)
    size_bytes = file.tell()
    file.seek(0)

    max_size = current_app.config.get("MAX_FILE_SIZE", 10 * 1024 * 1024)
    if size_bytes > max_size:
        return False, f"File size exceeds {max_size / (1024*1024)} MB."

    return True, None

def save_uploaded_file(file, prefix=""):
    """
    Save the uploaded file securely in the session-specific uploads folder.
    Returns the full file path and stored filename.
    """
    # Get session-specific upload folder
    upload_folder = get_session_folder(current_app.config.get('UPLOAD_FOLDER', 'uploads'))
    
    # Ensure upload directory exists
    os.makedirs(upload_folder, exist_ok=True)

    # Generate secure file names using the centralized function
    file_names = generate_file_names(file.filename)
    stored_name = file_names['stored_name']
    
    filepath = os.path.join(upload_folder, stored_name)
    file.save(filepath)
    
    logger.info(f"Saved uploaded file: {filepath}")
    return filepath, stored_name

def get_uploaded_files(request, prefix="", session_id=None):
    """
    Process uploaded files from Flask request and save to session folder.
    Returns list of (file_path, original_filename, stored_filename) tuples
    """
    if 'files' not in request.files:
        return None, "No files part in request", 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return None, "No files uploaded", 400

    saved_files = []
    for f in files:
        if f.filename == '':
            continue
            
        valid, err = validate_file(f)
        if not valid:
            # Cleanup any already saved files
            for file_path, _, _ in saved_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
            return None, err, 400

        filepath, stored_name = save_uploaded_file(f, prefix=prefix)
        saved_files.append((filepath, f.filename, stored_name))

    return saved_files, None, 200

def cleanup_files(file_paths):
    """
    Clean up temporary files safely.
    """
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            # Log but don't fail the entire operation
            logger.warning(f"Could not remove file {file_path}: {e}")

def ensure_directory_exists(directory_path):
    """
    Ensure a directory exists, create if it doesn't.
    """
    os.makedirs(directory_path, exist_ok=True)
    return directory_path

def get_file_size(file_path):
    """
    Get file size in bytes.
    """
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def is_file_locked(file_path):
    """
    Check if a file is locked/being used by another process.
    """
    try:
        with open(file_path, 'a+b') as f:
            pass
        return False
    except IOError:
        return True

def validate_file_size(file_path: str, max_size: int = 50 * 1024 * 1024) -> bool:
    """Validate that file size is within limits"""
    try:
        return os.path.getsize(file_path) <= max_size
    except OSError:
        return False

def validate_total_file_size(file_paths: List[str], max_total_size_mb: int = 10) -> Tuple[bool, str]:
    """Validate that total size of all files is within limits"""
    try:
        max_total_size_bytes = max_total_size_mb * 1024 * 1024
        total_size = 0
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                return False, f"File not found: {os.path.basename(file_path)}"
            
            file_size = os.path.getsize(file_path)
            total_size += file_size
            
            if total_size > max_total_size_bytes:
                return False, f"Total file size exceeds {max_total_size_mb}MB limit"
        
        return True, ""
    except Exception as e:
        logger.error(f"Error validating total file size: {e}")
        return False, "Error validating file sizes"

def cleanup_temp_files(file_paths: List[str], keep_uploaded: bool = True) -> None:
    """
    Clean up temporary files after processing.
    - keep_uploaded=True will not delete files inside UPLOAD_FOLDER.
    - Never delete files in PROCESSED_FOLDER.
    """
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    processed_folder = current_app.config.get('PROCESSED_FOLDER', 'processed')
    
    # Get absolute paths for comparison
    upload_folder_abs = os.path.abspath(upload_folder)
    processed_folder_abs = os.path.abspath(processed_folder)
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                file_path_abs = os.path.abspath(file_path)
                
                # NEVER delete files from processed folder
                if file_path_abs.startswith(processed_folder_abs):
                    continue
                
                # Skip user-uploaded files if keep_uploaded is True
                if keep_uploaded and file_path_abs.startswith(upload_folder_abs):
                    continue
                
                # Delete the file
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
                
        except Exception as e:
            logger.warning(f"Could not remove temporary file {file_path}: {e}")

def get_session_upload_folder():
    """Get the session-specific upload folder path"""
    return get_session_folder(current_app.config.get('UPLOAD_FOLDER', 'uploads'))

def get_session_processed_folder():
    """Get the session-specific processed folder path"""
    return get_session_folder(current_app.config.get('PROCESSED_FOLDER', 'processed'))

def get_session_previews_folder():
    """Get the session-specific previews folder path"""
    return get_session_folder(current_app.config.get('PREVIEWS_FOLDER', 'previews'))
