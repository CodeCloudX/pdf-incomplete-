# app.py
from flask import Flask, render_template, request, jsonify, send_from_directory, session, url_for, redirect, send_file
from werkzeug.utils import secure_filename
import os
import io
import re
import json
import logging
import shutil
import time
import hashlib
import threading
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from config import Config
from PyPDF2 import PdfReader
import zipfile
from functools import wraps

# Import generic tools and utilities
from tools.generic_tools import (
    execute_tool,
    generate_preview_thumbnails,
    get_pdf_page_count,
    allowed_file,
    validate_pdf_password,
    health_check
)
from utils.file_utils import save_uploaded_file, get_uploaded_files, cleanup_files
from utils.cleanup import cleanup_aged_files, init_cleanup_cli
from utils.file_naming_utils import rename_processed_files

# Import session-based file management
from utils.file_manager import ensure_session_id, get_session_folder
from utils.cleanup import manual_clear_session_folders, schedule_session_cleanup
from utils.file_utils import save_uploaded_file as session_save_uploaded_file

# Import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ----------------- Constants -----------------
DEFAULT_CONFIG = {
    'UPLOAD_FOLDER': 'uploads',
    'PROCESSED_FOLDER': 'processed',
    'PREVIEWS_FOLDER': 'previews'
}
SESSION_TIMEOUT_SECONDS = 600  # 10 minutes
CACHE_EXPIRY_MINUTES = 30
MAX_FILE_SIZE_MB = 10
MAX_FILES = 5
MERGE_MIN_FILES = 2

# ----------------- Initialize Flask -----------------
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('PDFMaster Pro startup')

logger = logging.getLogger(__name__)

# ----------------- Initialize APScheduler -----------------
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()
logger.info("APScheduler initialized")

# ----------------- Initialize App -----------------
Config.init_app(app)

# ----------------- Tools Dictionary -----------------
tools = {
    'split': {'id': 'split', 'name': 'Split PDF', 'description': 'Split your PDF into multiple files.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'merge': {'id': 'merge', 'name': 'Merge PDF', 'description': 'Combine multiple PDFs into one.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'compress': {'id': 'compress', 'name': 'Compress PDF', 'description': 'Reduce PDF file size.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'rotate': {'id': 'rotate', 'name': 'Rotate PDF', 'description': 'Rotate PDF pages.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'pdf-to-word': {'id': 'pdf-to-word', 'name': 'PDF to Word', 'description': 'Convert PDF to Word format.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'pdf-to-excel': {'id': 'pdf-to-excel', 'name': 'PDF to Excel', 'description': 'Convert PDF to Excel format.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'pdf-to-ppt': {'id': 'pdf-to-ppt', 'name': 'PDF to PowerPoint', 'description': 'Convert PDF to PowerPoint format.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'pdf-to-jpg': {'id': 'pdf-to-jpg', 'name': 'PDF to JPG', 'description': 'Convert PDF to JPG images.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'pdf-to-text': {'id': 'pdf-to-text', 'name': 'PDF to Text', 'description': 'Extract text from PDF.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'ocr': {'id': 'ocr', 'name': 'OCR PDF', 'description': 'Perform OCR on scanned PDF.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'unlock': {'id': 'unlock', 'name': 'Unlock PDF', 'description': 'Remove PDF password.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
    'protect': {'id': 'protect', 'name': 'Protect PDF', 'description': 'Add password to PDF.', 'max_files': MAX_FILES, 'max_size': MAX_FILE_SIZE_MB},
}

# ----------------- Preview Cache -----------------
PREVIEW_CACHE: Dict[str, Dict] = {}
CACHE_EXPIRY = timedelta(minutes=CACHE_EXPIRY_MINUTES)

# ----------------- Helper Functions -----------------
def get_session_context() -> str:
    """Get session context for logging"""
    session_id = session.get('session_id', 'no-session')
    return f"[SESSION:{session_id[:8]}]"

def format_file_size(file_path: str) -> str:
    """Format file size in human-readable format"""
    try:
        if not os.path.exists(file_path):
            return "File not found"
            
        size_bytes = os.path.getsize(file_path)
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes / (1024*1024):.2f} MB"
    except Exception as e:
        logger.error(f"{get_session_context()} Error getting file size for {file_path}: {e}")
        return "Unknown size"

def generate_file_hash(file_path: str) -> str:
    """Generate MD5 hash of file content for cache key"""
    try:
        if not os.path.exists(file_path):
            return f"missing_{os.path.basename(file_path)}"
            
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"{get_session_context()} Error generating file hash: {e}")
        return f"{os.path.basename(file_path)}_{os.path.getmtime(file_path) if os.path.exists(file_path) else 'missing'}"

def get_cached_previews(cache_key: str) -> Optional[Dict]:
    """Get cached previews if they exist and are not expired"""
    if cache_key in PREVIEW_CACHE:
        cache_entry = PREVIEW_CACHE[cache_key]
        if datetime.now() - cache_entry['timestamp'] < CACHE_EXPIRY:
            return cache_entry['previews']
        else:
            del PREVIEW_CACHE[cache_key]
    return None

def cache_previews(cache_key: str, thumbnails: List[str], page_count: int) -> None:
    """Cache previews for future use"""
    PREVIEW_CACHE[cache_key] = {
        'previews': {'thumbnails': thumbnails, 'page_count': page_count},
        'timestamp': datetime.now()
    }

def cleanup_expired_preview_cache() -> int:
    """Clean up expired cache entries"""
    current_time = datetime.now()
    expired_keys = [
        key for key, entry in PREVIEW_CACHE.items()
        if current_time - entry['timestamp'] > CACHE_EXPIRY
    ]
    for key in expired_keys:
        del PREVIEW_CACHE[key]
    return len(expired_keys)

def validate_uploaded_files(files: List, tool_id: str) -> Tuple[bool, Optional[str]]:
    """Validate uploaded files against tool-specific limits"""
    tool = tools.get(tool_id)
    if not tool:
        return False, "Invalid tool"
    
    # Check file count
    if len(files) > tool['max_files']:
        return False, f"Too many files. Maximum {tool['max_files']} file(s) allowed."
    
    # Check individual file sizes
    max_size_bytes = tool['max_size'] * 1024 * 1024
    
    total_size = 0
    for file in files:
        try:
            if hasattr(file, 'seek') and hasattr(file, 'tell'):
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
            else:
                file_size = os.path.getsize(file)
            
            # Check individual file size
            if file_size > max_size_bytes:
                filename = getattr(file, 'filename', os.path.basename(file))
                return False, f"File '{filename}' exceeds {tool['max_size']}MB size limit."
            
            # Check total size
            total_size += file_size
            if total_size > max_size_bytes:
                return False, f"Total size of all files exceeds {tool['max_size']}MB limit."
                
        except Exception as e:
            filename = getattr(file, 'filename', 'unknown')
            return False, f"Error checking file size for {filename}: {e}"
    
    return True, None

def validate_file_count_for_tool(files: List, tool_id: str) -> Tuple[bool, Optional[str]]:
    """Special validation for tools that require specific file counts"""
    tool = tools.get(tool_id)
    if not tool:
        return False, "Invalid tool"
    
    # Merge requires at least 2 files
    if tool_id == "merge" and len(files) < MERGE_MIN_FILES:
        return False, "Merge requires at least 2 PDF files."
    
    # Other tools can have 1-5 files
    if len(files) < 1:
        return False, "Please upload at least 1 file."
    
    if len(files) > tool['max_files']:
        return False, f"Too many files. Maximum {tool['max_files']} file(s) allowed."
    
    return True, None

# ----------------- Decorators -----------------
def validate_tool_id(f):
    """Decorator to validate tool_id parameter"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tool_id = kwargs.get('tool_id')
        if tool_id not in tools:
            logger.warning(f"{get_session_context()} Invalid tool ID requested: {tool_id}")
            return render_template('errors/404.html'), 404
        return f(*args, **kwargs)
    return decorated_function

# ----------------- Session Data Model -----------------
class SessionData:
    """Centralized session data management"""
    
    def __init__(self):
        self.processed_files: List[str] = [] # List of stored filenames
        self.processed_files_details: List[Dict[str, str]] = [] # List of dicts: {'stored_name': '...', 'display_name': '...'}
        self.file_times: Dict[str, float] = {}
        self.countdown: Dict[str, Any] = {
            'start_time': time.time(),
            'end_time': time.time() + SESSION_TIMEOUT_SECONDS,
            'active': True
        }
        self.preview_data: Dict[str, Any] = {}
        self.session_id: str = ensure_session_id()
    
    def update_countdown(self) -> None:
        """Reset countdown timer"""
        self.countdown = {
            'start_time': time.time(),
            'end_time': time.time() + SESSION_TIMEOUT_SECONDS,
            'active': True
        }
    
    def clear_processed_files(self) -> None:
        """Clear processed files list"""
        self.processed_files = []
        self.processed_files_details = []
        self.file_times = {}

# ----------------- Session Initialization -----------------
@app.before_request
def initialize_session():
    """Initialize session variables using SessionData model"""
    try:
        if 'session_data' not in session:
            session_data = SessionData()
            session['session_data'] = session_data.__dict__
            logger.info(f"{get_session_context()} Initialized new session")
        elif 'countdown' not in session.get('session_data', {}):
            # Migrate old session format to new if 'countdown' is missing
            session_data = SessionData()
            # Attempt to preserve existing processed files if they were in old format
            session_data.processed_files = session.get('processed_files', [])
            session_data.file_times = session.get('file_times', {})
            # If processed_files_details was not present, initialize it
            if 'processed_files_details' not in session.get('session_data', {}):
                session_data.processed_files_details = [{'stored_name': f, 'display_name': f} for f in session_data.processed_files]
            
            session['session_data'] = session_data.__dict__
            logger.info(f"{get_session_context()} Migrated old session format")
            
        # Ensure session_id is set
        if 'session_id' not in session:
            session['session_id'] = ensure_session_id()
            
    except Exception as e:
        logger.error(f"Error initializing session: {e}")
        # Create minimal session data
        session['session_id'] = ensure_session_id()
        session['session_data'] = SessionData().__dict__

# ------------------- Generic Processing -------------------
def generic_process(tool_id: str, uploaded_files: Optional[List[str]] = None,
                   page_selection: Optional[Dict] = None, tool_options: Optional[Dict] = None) -> Tuple[Any, int]:
    """Main processing function for all tools"""
    try:
        logger.info(f"{get_session_context()} Processing tool: {tool_id}")
        
        # Handle file uploads
        if uploaded_files is None:
            # Use session data
            preview_data = session.get('preview_data', {})
            uploaded_files_paths = [fp for fp, _, _ in preview_data.get('temp_files', [])]
            
            # Fallback to direct file upload
            if not uploaded_files_paths and request.files:
                request_files = request.files.getlist("files")
                if request_files:
                    uploaded_files_paths = []
                    for file in request_files:
                        if file and file.filename and allowed_file(file.filename):
                            save_path, stored_name = session_save_uploaded_file(file, session['session_id'])
                            uploaded_files_paths.append(save_path)
            uploaded_files = uploaded_files_paths

        # Validate we have files to process
        if not uploaded_files:
            logger.error(f"{get_session_context()} No files to process")
            return jsonify({"status": "error", "message": "No files uploaded or session expired"}), 400

        # Password protected check (skip for unlock tool)
        if tool_id != "unlock":
            for pdf_path in uploaded_files:
                try:
                    if not os.path.exists(pdf_path):
                        logger.warning(f"{get_session_context()} File not found: {pdf_path}")
                        continue
                        
                    with open(pdf_path, "rb") as f:
                        reader = PdfReader(f)
                        if reader.is_encrypted:
                            logger.warning(f"{get_session_context()} Rejected password protected PDF for tool {tool_id}: {pdf_path}")
                            return jsonify({
                                "status": "error",
                                "message": "You cannot upload password-protected PDF files. Please use the 'Unlock PDF' tool first."
                            }), 400

                except Exception as e:
                    logger.error(f"{get_session_context()} Error checking encryption for {pdf_path}: {e}")
                    return jsonify({
                        "status": "error",
                        "message": f"Invalid or corrupted PDF: {os.path.basename(pdf_path)}"
                    }), 400

        # Parse page selection from form data
        if page_selection is None:
            page_selection = {}
            for key in request.form:
                if key.startswith("selected_pages_"):
                    filename = key.replace("selected_pages_", "")
                    pages_str = request.form.get(key, "")
                    if pages_str:
                        try:
                            pages = [int(p.strip()) for p in pages_str.split(",") if p.strip().isdigit()]
                            page_selection[filename] = pages
                            logger.info(f"{get_session_context()} Page selection for {filename}: {pages}")
                        except Exception as e:
                            logger.warning(f"{get_session_context()} Invalid page selection for {filename}: {pages_str} - {e}")
                            page_selection[filename] = []
                    else:
                        page_selection[filename] = []

        # Get all tool options from form if not already provided
        if tool_options is None:
            tool_options = {}
            for key in request.form:
                if not key.startswith("selected_pages_"):
                    tool_options[key] = request.form.get(key)
            
            # Special handling for boolean values from checkboxes/radios
            if tool_id == 'protect':
                tool_options['allow_printing'] = tool_options.get('allow_printing') == 'on' or tool_options.get('allow_printing') == 'true'
                tool_options['allow_copying'] = tool_options.get('allow_copying') == 'on' or tool_options.get('allow_copying') == 'true'
                tool_options['allow_modification'] = tool_options.get('allow_modification') == 'on' or tool_options.get('allow_modification') == 'true'
                if 'password' not in tool_options:
                    tool_options['password'] = request.form.get('password')

            if tool_id == 'unlock':
                if 'password' not in tool_options:
                    tool_options['password'] = request.form.get('password')

        # Handle file order for merge tool
        if tool_id == "merge":
            file_order_str = request.form.get('file_order')
            if file_order_str:
                try:
                    file_order = json.loads(file_order_str)
                    logger.info(f"{get_session_context()} File order for merge: {file_order}")
                    
                    # Reorder files based on file_order
                    file_map = {os.path.basename(f): f for f in uploaded_files}
                    try:
                        uploaded_files = [file_map[f] for f in file_order if f in file_map]
                        logger.info(f"{get_session_context()} Reordered files: {[os.path.basename(f) for f in uploaded_files]}")
                    except KeyError as e:
                        logger.warning(f"{get_session_context()} File not found in file order: {e}, using original order")
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"{get_session_context()} Invalid file order format, using original order")
            
            # Add file_order to tool_options for merge tool
            tool_options['file_order'] = file_order if 'file_order' in locals() else []

        # Execute the tool with all options
        logger.info(f"{get_session_context()} Executing {tool_id} with {len(uploaded_files)} files")
        
        password_for_execute_tool = tool_options.get('password') if tool_id in ['unlock', 'protect'] else None

        # Pass session ID to tools for proper file storage
        tool_options['session_id'] = session['session_id']
        
        result = execute_tool(tool_id, uploaded_files, page_selection, password_for_execute_tool, tool_options)

        # Validate the result structure
        if not result or not isinstance(result, dict) or 'status' not in result:
            logger.error(f"{get_session_context()} Invalid result structure from execute_tool: {result}")
            result = {
                'status': 'error',
                'message': 'Internal processing error. Please try again.'
            }
         
        if result.get('status') == 'error':
            logger.error(f"{get_session_context()} Tool execution failed: {result.get('message')}")
            return jsonify(result), 400

        # Return success response
        response_data = {
            "status": "success",
            "tool": tool_id,
            "message": result.get('message', f"Successfully processed {len(uploaded_files)} files"),
            "redirect_url": f"/tool/{tool_id}/download",
            "result": result
        }
        
        logger.info(f"{get_session_context()} Tool {tool_id} completed successfully")
        return jsonify(response_data), 200

    except Exception as e:
        logger.exception(f"{get_session_context()} Error processing tool '{tool_id}': {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Internal server error while processing. Please try again."
        }), 500
    
# ----------------- Initialize Cleanup System -----------------
init_cleanup_cli(app)

# Global flag for scheduler
cleanup_scheduler_started = False

@app.before_request
def start_cleanup_scheduler():
    global cleanup_scheduler_started
    if not cleanup_scheduler_started:
        cleanup_scheduler_started = True
        
        # Schedule cleanup job
        try:
            scheduler.add_job(
                func=run_cleanup,
                trigger=IntervalTrigger(minutes=10),
                id='cleanup_job',
                name='Scheduled file cleanup',
                replace_existing=True
            )
            logger.info("Cleanup scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start cleanup scheduler: {e}")

def run_cleanup():
    """Run cleanup with app context"""
    with app.app_context():
        try:
            UPLOAD_FILE_RETENTION_MINUTES = 10
            PREVIEW_FILE_RETENTION_MINUTES = 10
            PROCESSED_FILE_RETENTION_MINUTES = 10

            deleted_files = cleanup_aged_files(
                upload_max_age_minutes=UPLOAD_FILE_RETENTION_MINUTES,
                preview_max_age_minutes=PREVIEW_FILE_RETENTION_MINUTES,
                processed_max_age_minutes=PROCESSED_FILE_RETENTION_MINUTES
            )
            
            if deleted_files > 0:
                logger.info(f"Scheduled cleanup: {deleted_files} files deleted.")
            else:
                logger.debug("Scheduled cleanup: No files to clean up")
                
        except Exception as e:
            logger.error(f"Scheduled cleanup failed: {e}")

# ----------------- Global Context -----------------
@app.context_processor
def inject_now():
    return {
        "current_year": datetime.now().year,
        "tools": tools,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "max_files": MAX_FILES,
        "merge_min_files": MERGE_MIN_FILES
    }

# ----------------- Routes -----------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify(health_check())

@app.route('/tools')
def tools_page():
    """Display all available tools"""
    return render_template('tools.html', tools=tools)

@app.route('/about')
def about_page():
    """About page"""
    return render_template('about.html')

@app.route('/contact')
def contact_page():
    """Contact page"""
    return render_template('contact.html')

@app.route('/tool-page/<tool_id>')
@validate_tool_id
def tool_page_old(tool_id):
    tool = tools.get(tool_id)
    if not tool:
        return render_template("errors/404.html"), 404
    return render_template('upload.html', tool=tool)

@app.route('/tool/<tool_id>')
@validate_tool_id
def tool_page(tool_id):
    return redirect(url_for('tool_page_old', tool_id=tool_id))

# Define the placeholder filename.
PLACEHOLDER_FILENAME = "no_preview_available.jpg"

@app.route('/previews/<filename>')
def serve_preview(filename):
    """
    Serve preview images. If the filename is the placeholder,
    serve it from the static/images directory. Otherwise, serve
    from the configured PREVIEWS_FOLDER.
    """
    try:
        if filename == PLACEHOLDER_FILENAME:
            return send_from_directory(os.path.join(app.root_path, 'static', 'images'), PLACEHOLDER_FILENAME)
        else:
            # FIXED: Correct usage
            previews_folder = get_session_folder(app.config.get('PREVIEWS_FOLDER', 'previews'))
            return send_from_directory(previews_folder, filename)

    except Exception as e:
        logger.error(f"{get_session_context()} Error serving preview for {filename}: {e}")
        return render_template('errors/500.html'), 500

# ----------------- Cleanup on Startup -----------------
def cleanup_on_startup():
    """Clean up any leftover files when the server starts"""
    try:
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        if os.path.exists(processed_folder):
            processed_files = os.listdir(processed_folder)
            for filename in processed_files:
                file_path = os.path.join(processed_folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file on startup: {filename}")
        
        upload_folder = app.config.get('UPLOAD_FOLDER', DEFAULT_CONFIG['UPLOAD_FOLDER'])
        if os.path.exists(upload_folder):
            upload_files = os.listdir(upload_folder)
            for filename in upload_files:
                file_path = os.path.join(upload_folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                
        logger.info("Server startup cleanup completed")
    except Exception as e:
        logger.error(f"Error during startup cleanup: {e}")

cleanup_on_startup()

# ----------------- Preview Route -----------------
@app.route("/tool/<tool_id>/preview", methods=["POST"])
@validate_tool_id
def tool_preview(tool_id):
    try:
        # Ensure session ID exists
        session_id = ensure_session_id()
        
        uploaded_files_data, error_msg, status_code = get_uploaded_files(request, prefix=f"preview_{tool_id}_", session_id=session_id)
        if error_msg:
            return jsonify({"error": error_msg}), status_code
         
        # Check for encrypted files (skip for unlock tool)
        encrypted_files = []
        if tool_id != 'unlock': 
            for file_path, original_filename, stored_filename in uploaded_files_data:
                try:
                    if not os.path.exists(file_path):
                        logger.warning(f"{get_session_context()} File not found: {file_path}")
                        continue
                        
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    reader = PdfReader(io.BytesIO(file_bytes))
                    if reader.is_encrypted:
                        encrypted_files.append(original_filename)
                        logger.info(f"{get_session_context()} Found encrypted file: {original_filename}")
                except Exception as e:
                    logger.warning(f"{get_session_context()} Error checking file encryption for {file_path}: {e}")

        # If there are encrypted files and it's not the unlock tool, show error
        if encrypted_files and tool_id != 'unlock':
            cleanup_files([fp for fp, _, _ in uploaded_files_data])
            return jsonify({
                "error": "You cannot upload password-protected PDF files. Please use the 'Unlock PDF' tool first.",
                "encrypted_filenames": encrypted_files
            }), 400

        is_valid, validation_error = validate_file_count_for_tool([fp for fp, _, _ in uploaded_files_data], tool_id)
        if not is_valid:
            cleanup_files([fp for fp, _, _ in uploaded_files_data])
            return jsonify({"error": validation_error}), 400

        is_valid, validation_error = validate_uploaded_files([fp for fp, _, _ in uploaded_files_data], tool_id)
        if not is_valid:
            cleanup_files([fp for fp, _, _ in uploaded_files_data])
            return jsonify({"error": validation_error}), 400

        password = request.form.get("password", "").strip()
        previews = []
        temp_files = []

        for file_path, original_filename, stored_filename in uploaded_files_data:
            filename = os.path.basename(file_path)
            temp_files.append((file_path, original_filename, stored_filename))

            file_hash = generate_file_hash(file_path)
            cache_key = f"{file_hash}_{password}"
            
            cached_previews = get_cached_previews(cache_key)
            
            if cached_previews:
                logger.info(f"{get_session_context()} Using cached previews for {original_filename}")
                thumbs = cached_previews['thumbnails']
                page_count = cached_previews['page_count']
            else:
                logger.info(f"{get_session_context()} Generating new previews for {original_filename}")
                
                # SKIP PREVIEW GENERATION FOR ENCRYPTED FILES AND UNLOCK TOOL
                skip_preview = False
                if tool_id == 'unlock':
                    skip_preview = True
                    logger.info(f"{get_session_context()} Skipping preview generation for unlock tool: {original_filename}")
                else:
                    # Check if file is encrypted
                    try:
                        with open(file_path, "rb") as f:
                            reader = PdfReader(f)
                            if reader.is_encrypted:
                                skip_preview = True
                                logger.info(f"{get_session_context()} Skipping preview generation for encrypted file: {original_filename}")
                    except Exception as e:
                        logger.warning(f"{get_session_context()} Error checking encryption for preview: {e}")
                
                if skip_preview:
                    # Don't generate previews, just get page count
                    thumbs = []
                    page_count = get_pdf_page_count(file_path)
                    logger.info(f"{get_session_context()} Skipped preview generation, got page count: {page_count}")
                    thumbs = [PLACEHOLDER_FILENAME] * page_count if page_count > 0 else []
                else:
                    # Generate normal previews
                    preview_password = password if tool_id == 'unlock' else None
                    
                    previews_folder = get_session_folder(app.config.get('PREVIEWS_FOLDER', 'previews'))
                    thumbs = generate_preview_thumbnails(
                        file_path,
                        previews_folder,
                        max_pages=None,
                        password=preview_password,
                        skip_if_encrypted=True
                    )
                    page_count = get_pdf_page_count(file_path)
                
                cache_previews(cache_key, thumbs, page_count)

            previews.append({
                "name": filename,
                "original_name": original_filename,
                "stored_name": stored_filename,
                "thumbnails": thumbs,
                "page_count": page_count,
                "file_hash": file_hash,
                "size": format_file_size(file_path),
                "is_encrypted": skip_preview if 'is_encrypted' in locals() else False # Corrected variable name
            })

        session['preview_data'] = {
            "files": previews,
            "tool_id": tool_id,
            "password": password,
            "temp_files": temp_files,
            "cache_keys": [f"{p['file_hash']}_{password}" for p in previews]
        }

        current_tool = tools.get(tool_id, {})
        
        return render_template(
            "preview-process.html",
            files=previews,
            tool_id=tool_id,
            tool_name=current_tool.get('name', 'PDF Tool'),
            tool=current_tool,
            password=password
        )

    except Exception as e:
        logger.error(f"{get_session_context()} Preview route failed: {e}")
        if 'temp_files' in locals():
            cleanup_files([fp for fp, _, _ in temp_files])
        return jsonify({"error": "Error generating preview. Please try again."}), 500

# ----------------- Remove File Route -----------------
@app.route('/remove-file', methods=['POST'])
def remove_file():
    """Remove a file from the session and filesystem using filename"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        file_index = data.get('file_index')
        original_filename = data.get('filename')
        
        if file_index is None or not original_filename:
            return jsonify({"error": "File index and filename are required"}), 400
        
        preview_data = session.get('preview_data', {})
        temp_files = preview_data.get('temp_files', [])
        files = preview_data.get('files', [])
        
        if int(file_index) >= len(temp_files) or int(file_index) >= len(files):
            return jsonify({"error": "Invalid file index"}), 400
        
        file_path_to_remove, _, _ = temp_files[int(file_index)]
        
        if os.path.exists(file_path_to_remove):
            os.remove(file_path_to_remove)
            logger.info(f"{get_session_context()} Removed file: {file_path_to_remove}")
        
        temp_files.pop(int(file_index))
        files.pop(int(file_index))
        
        preview_data['temp_files'] = temp_files
        preview_data['files'] = files
        session['preview_data'] = preview_data
        
        return jsonify({
            "success": True,
            "message": f"File {original_filename} removed successfully",
            "files": files,
            "remaining_files": len(files)
        })
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error removing file: {e}")
        return jsonify({"error": f"Failed to remove file: {str(e)}"}), 500

# ----------------- Process Unlock Route -----------------
@app.route('/process/unlock', methods=['POST'])
def process_unlock():
    """Handle unlock processing requests from the frontend"""
    try:
        preview_data = session.get('preview_data', {})
        if not preview_data:
            logger.error(f"{get_session_context()} No preview data in session for unlock tool")
            return jsonify({"status": "error", "message": "Session expired. Please upload files again."}), 400
        
        uploaded_files_paths = [fp for fp, _, _ in preview_data.get('temp_files', [])]
        
        if not uploaded_files_paths:
            logger.error(f"{get_session_context()} No files found in session for unlock")
            return jsonify({"status": "error", "message": "No files to process. Please upload files first."}), 400
        
        tool_options = {'password': request.form.get('password')}
        
        response, status_code = generic_process('unlock', uploaded_files=uploaded_files_paths, tool_options=tool_options)
        return response, status_code
        
    except Exception as e:
        logger.error(f"{get_session_context()} Unlock processing error: {str(e)}", exc_info=True)
        preview_data = session.get('preview_data', {})
        uploaded_files_paths = [fp for fp, _, _ in preview_data.get('temp_files', [])]
        cleanup_files(uploaded_files_paths)
        return jsonify({"status": "error", "message": f"Error processing unlock: {str(e)}"}), 500

# ----------------- Process Tool -----------------
@app.route('/tool/<tool_id>/process', methods=['POST'])
@validate_tool_id
def process_tool(tool_id):
    try:
        preview_data = session.get('preview_data', {})
        if not preview_data:
            logger.error(f"{get_session_context()} No preview data in session - session may have expired")
            return jsonify({"status": "error", "message": "Session expired. Please upload files again."}), 400
        
        uploaded_files_paths = [fp for fp, _, _ in preview_data.get('temp_files', [])]
        
        if not uploaded_files_paths:
            logger.error(f"{get_session_context()} No files found in session")
            return jsonify({"status": "error", "message": "No files to process"}), 400
        
        for file_path in uploaded_files_paths:
            if not os.path.exists(file_path):
                logger.error(f"{get_session_context()} File not found: {file_path}")
                return jsonify({"status": "error", "message": "Uploaded files no longer exist. Please upload again."}), 400
        
        # Get list of existing files before processing
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        session_folder = get_session_folder(processed_folder)
        existing_files = set()
        if os.path.exists(session_folder):
            existing_files = set(os.listdir(session_folder))
        
        tool_options = {}
        for key in request.form:
            if not key.startswith("selected_pages_"):
                tool_options[key] = request.form.get(key)
        
        if tool_id == 'protect':
            tool_options['allow_printing'] = tool_options.get('allow_printing') == 'on' or tool_options.get('allow_printing') == 'true'
            tool_options['allow_copying'] = tool_options.get('allow_copying') == 'on' or tool_options.get('allow_copying') == 'true'
            tool_options['allow_modification'] = tool_options.get('allow_modification') == 'on' or tool_options.get('allow_modification') == 'true'
            if 'password' not in tool_options:
                tool_options['password'] = request.form.get('password')

        if tool_id == 'unlock':
            if 'password' not in tool_options:
                tool_options['password'] = request.form.get('password')

        # Execute the tool
        response, status_code = generic_process(tool_id, uploaded_files=uploaded_files_paths, tool_options=tool_options)
        
        if status_code == 200:
            # Scan for new files created during processing
            if os.path.exists(session_folder):
                current_files = set(os.listdir(session_folder))
                new_files = current_files - existing_files
                
                session_data = session.get('session_data', {})
                if 'processed_files' not in session_data:
                    session_data['processed_files'] = []
                if 'processed_files_details' not in session_data:
                    session_data['processed_files_details'] = []
                
                # Determine which files to add to session tracking
                files_to_track = []
                for filename in new_files:
                    # Heuristic to decide if a file should be tracked individually
                    # For 'pdf-to-jpg', 'split', 'ocr', 'pdf-to-text', 'pdf-to-word', 'pdf-to-excel', 'pdf-to-ppt'
                    # individual files are expected. For others, usually one PDF or a ZIP.
                    
                    # If a ZIP file is generated, and it's not a tool specifically for ZIP output (like 'pdf-to-jpg' which might zip multiple images),
                    # then we might want to prioritize the PDF output or handle the ZIP as a "download all" option.
                    
                    # For 'rotate', 'compress', 'merge', 'unlock', 'protect', usually a single PDF is the primary output.
                    # If a ZIP is also generated, it might be an artifact or a secondary download.
                    
                    # Let's prioritize non-zip files for individual display, unless the tool is specifically for zip output.
                    if filename.lower().endswith('.zip'):
                        # If the tool is 'pdf-to-jpg' and it produces a zip, we might want to track the zip.
                        # Otherwise, if a PDF is also produced, prioritize the PDF.
                        if tool_id == 'pdf-to-jpg': # Or other tools that produce multiple files zipped
                            files_to_track.append(filename)
                        else:
                            # For tools like rotate, compress, merge, if a zip is produced, it's likely secondary.
                            # We'll rely on the PDF output if available.
                            pass # Don't add zip if a PDF is expected as primary
                    else: # It's a non-zip file (e.g., PDF, DOCX, TXT, JPG)
                        files_to_track.append(filename)

                # Add selected new files to session tracking
                for filename in files_to_track:
                    if filename not in session_data['processed_files']:
                        session_data['processed_files'].append(filename)
                        
                        # Determine display name for the file
                        display_name = filename
                        # Try to get original name from preview_data if available
                        if 'preview_data' in session:
                            for file_info in preview_data.get('files', []):
                                if file_info.get('stored_name') == filename:
                                    display_name = file_info.get('original_name', filename)
                                    break
                        
                        # Heuristic for tool-specific naming (e.g., remove tool_id_hash_)
                        if '_' in filename and filename.startswith(tuple(t['id'] for t in tools.values())):
                            parts = filename.split('_')
                            if len(parts) > 2:
                                temp_display_name = '_'.join(parts[2:])
                                if temp_display_name:
                                    display_name = temp_display_name
                        
                        # Ensure display name has correct extension
                        if not display_name.lower().endswith(('.pdf', '.zip', '.docx', '.xlsx', '.pptx', '.jpg', '.txt')):
                            ext = os.path.splitext(filename)[1]
                            if ext:
                                display_name += ext
                            else: # Fallback if no extension found
                                if tool_id in ['split', 'merge', 'compress', 'rotate', 'unlock', 'protect', 'ocr']:
                                    display_name += '.pdf'
                                elif tool_id == 'pdf-to-word':
                                    display_name += '.docx'
                                elif tool_id == 'pdf-to-excel':
                                    display_name += '.xlsx'
                                elif tool_id == 'pdf-to-ppt':
                                    display_name += '.pptx'
                                elif tool_id == 'pdf-to-jpg':
                                    display_name += '.jpg'
                                elif tool_id == 'pdf-to-text':
                                    display_name += '.txt'

                        session_data['processed_files_details'].append({
                            'stored_name': filename,
                            'display_name': display_name
                        })
                        
                    # Store file creation time
                    file_path = os.path.join(session_folder, filename)
                    if os.path.exists(file_path):
                        if 'file_times' not in session_data:
                            session_data['file_times'] = {}
                        session_data['file_times'][filename] = os.path.getmtime(file_path)
                
                session['session_data'] = session_data
                logger.info(f"{get_session_context()} Added {len(files_to_track)} new files to session tracking: {files_to_track}")

            cache_keys = preview_data.get('cache_keys', [])
            for key in cache_keys:
                if key in PREVIEW_CACHE:
                    del PREVIEW_CACHE[key]
                    logger.info(f"{get_session_context()} Removed cached previews for key: {key}")
            
            if 'preview_data' in session:
                session.pop('preview_data')
            
            # Start countdown for this session
            session_data = session.get('session_data', {})
            session_data['countdown'] = {
                'start_time': time.time(),
                'end_time': time.time() + SESSION_TIMEOUT_SECONDS,
                'active': True
            }
            session['session_data'] = session_data
            logger.info(f"{get_session_context()} Countdown started for session")
            
            return redirect(url_for('download_page', tool_id=tool_id))
        
        # If there was an error, return the error response
        return response
        
    except Exception as e:
        logger.error(f"{get_session_context()} Processing error: {str(e)}", exc_info=True)
        preview_data = session.get('preview_data', {})
        uploaded_files_paths = [fp for fp, _, _ in preview_data.get('temp_files', [])]
        return jsonify({"status": "error", "message": f"Error processing files: {str(e)}"}), 500

# ----------------- Download Routes -----------------
@app.route('/download/processed/<filename>')
def download_processed_file(filename):
    """Serve processed files for download"""
    try:
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        session_folder = get_session_folder(processed_folder)
        file_path = os.path.join(session_folder, filename)
        
        if os.path.exists(file_path):
            display_name = filename # Default to filename
            session_data = session.get('session_data', {})
            for f_info in session_data.get('processed_files_details', []):
                if f_info.get('stored_name') == filename:
                    display_name = f_info.get('display_name', filename)
                    break
            
            # Ensure display_name has an extension, if not, add based on filename
            if not os.path.splitext(display_name)[1]:
                original_ext = os.path.splitext(filename)[1]
                if original_ext:
                    display_name += original_ext

            return send_file(
                file_path, 
                as_attachment=True,
                download_name=display_name
            )
        else:
            return render_template('errors/404.html'), 404
    except Exception as e:
        logger.error(f"{get_session_context()} Error downloading file {filename}: {e}")
        return render_template('errors/500.html'), 500

@app.route('/tool/<tool_id>/download')
@validate_tool_id
def download_page(tool_id):
    tool = tools.get(tool_id)
    if not tool:
        return render_template('errors/404.html'), 404

    processed_files = []
    try:
        session_data = session.get('session_data', {})
        
        # Ensure processed_files_details exists and is up-to-date with actual files
        if 'processed_files_details' not in session_data:
            session_data['processed_files_details'] = []
        
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        session_folder = get_session_folder(processed_folder)
        
        # Re-validate processed_files_details against actual files on disk
        valid_processed_files_details = []
        for f_detail in session_data.get('processed_files_details', []):
            stored_name = f_detail.get('stored_name')
            if stored_name:
                file_path = os.path.join(session_folder, stored_name)
                if os.path.isfile(file_path):
                    # Update file_times if necessary
                    if stored_name not in session_data.get('file_times', {}):
                        if 'file_times' not in session_data:
                            session_data['file_times'] = {}
                        session_data['file_times'][stored_name] = os.path.getmtime(file_path)
                    
                    file_mtime = session_data['file_times'][stored_name]
                    
                    # Use the display_name from session_data, or fallback to stored_name
                    display_name = f_detail.get('display_name', stored_name)
                    
                    processed_files.append({
                        'name': stored_name,
                        'display_name': display_name,
                        'size': format_file_size(file_path),
                        'upload_time': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'download_url': url_for('download_processed_file', filename=stored_name),
                        'tool_used': tool['name'],
                        'processed_time': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
                    valid_processed_files_details.append(f_detail)
                else:
                    logger.warning(f"{get_session_context()} Processed file {stored_name} not found on disk, removing from session tracking.")
            
        # Update session with validated details
        session_data['processed_files'] = [f['stored_name'] for f in valid_processed_files_details] # Keep list of just names
        session_data['processed_files_details'] = valid_processed_files_details # Store richer details
        session['session_data'] = session_data
        
        # Check countdown status
        countdown = session_data.get('countdown', {})
        remaining_time = max(0, countdown.get('end_time', 0) - time.time())
        
        message = f"Your {tool['name']} operation was completed successfully!"
        
        return render_template(
            'download-page.html',
            tool=tool,
            tool_id=tool_id,
            tool_name=tool['name'],
            message=message,
            files=processed_files,
            countdown=countdown,
            remaining_time=int(remaining_time)
        )
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error loading download page: {e}")
        return render_template('errors/500.html'), 500
    
@app.route('/download/zip')
def download_zip():
    """Download all processed files as a zip archive"""
    try:
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        session_folder = get_session_folder(processed_folder)
        files_in_folder = os.listdir(session_folder) if os.path.exists(session_folder) else []
        
        if not files_in_folder:
            return jsonify({"status": "error", "message": "No files available for ZIP download."}), 404
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            session_data = session.get('session_data', {})
            processed_files_details = session_data.get('processed_files_details', [])
            
            for filename in files_in_folder:
                file_path = os.path.join(session_folder, filename)
                if os.path.isfile(file_path):
                    display_name_in_zip = filename # Default
                    for file_info in processed_files_details:
                        if file_info.get('stored_name') == filename:
                            display_name_in_zip = file_info.get('display_name', filename)
                            break
                    
                    zf.write(file_path, display_name_in_zip)
        
        memory_file.seek(0)
        
        zip_filename = f"processed_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        # Return the actual send_file response
        response = send_file(
            memory_file,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        # Add Content-Disposition header for filename in frontend
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{zip_filename}"
        return response
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error creating zip file: {e}")
        return jsonify({"status": "error", "message": f"Error creating zip file: {str(e)}"}), 500

# ----------------- Countdown Status -----------------
@app.route('/countdown/status')
def countdown_status():
    """Get countdown status for current session"""
    try:
        session_data = session.get('session_data', {})
        countdown = session_data.get('countdown', {})
        remaining_time = max(0, countdown.get('end_time', 0) - time.time())
        
        return jsonify({
            "status": "success",
            "remaining_time": int(remaining_time),
            "active": countdown.get('active', False)
        })
    except Exception as e:
        logger.error(f"{get_session_context()} Error getting countdown status: {e}")
        return jsonify({"status": "error", "message": "Error getting countdown status"}), 500

# ----------------- Rename File -----------------
@app.route('/rename/file/<filename>', methods=['POST'])
def rename_file(filename):
    """Rename a processed file"""
    try:
        data = request.get_json()
        if not data or 'new_name' not in data:
            return jsonify({"status": "error", "message": "New name required"}), 400
            
        new_display_name_raw = data['new_name'].strip()
        
        # Get original extension from the stored filename
        original_ext = os.path.splitext(filename)[1]
        
        # Construct the new stored filename with the original extension
        new_stored_name = new_display_name_raw + original_ext
            
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        session_folder = get_session_folder(processed_folder)
        old_path = os.path.join(session_folder, filename)
        new_path = os.path.join(session_folder, new_stored_name)
        
        if not os.path.exists(old_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        if os.path.exists(new_path):
            return jsonify({"status": "error", "message": "File with that name already exists"}), 400
            
        os.rename(old_path, new_path)
        
        # Update session data
        session_data = session.get('session_data', {})
        
        # Update processed_files list
        if filename in session_data.get('processed_files', []):
            idx = session_data['processed_files'].index(filename)
            session_data['processed_files'][idx] = new_stored_name
            
        # Update file_times
        if filename in session_data.get('file_times', {}):
            session_data['file_times'][new_stored_name] = session_data['file_times'].pop(filename)
            
        # Update processed_files_details
        for f_info in session_data.get('processed_files_details', []):
            if f_info.get('stored_name') == filename:
                f_info['stored_name'] = new_stored_name
                f_info['display_name'] = new_display_name_raw + original_ext # Display name should include extension
                break
            
        session['session_data'] = session_data
        
        return jsonify({
            "status": "success",
            "message": "File renamed successfully",
            "new_name": new_stored_name, # The actual new filename on server
            "new_display_name": new_display_name_raw + original_ext, # The name to display in UI (with extension)
            "new_download_url": url_for('download_processed_file', filename=new_stored_name)
        })
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error renaming file {filename}: {e}")
        return jsonify({"status": "error", "message": f"Error renaming file: {str(e)}"}), 500

# ----------------- Cleanup Single File -----------------
@app.route('/cleanup/file/<filename>', methods=['DELETE'])
def cleanup_single_file(filename):
    """Clean up a single processed file"""
    try:
        processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
        session_folder = get_session_folder(processed_folder)
        file_path = os.path.join(session_folder, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        os.remove(file_path)
        
        # Update session data
        session_data = session.get('session_data', {})
        
        # Remove from processed_files list
        if filename in session_data.get('processed_files', []):
            session_data['processed_files'].remove(filename)
            
        # Remove from file_times
        if filename in session_data.get('file_times', {}):
            session_data['file_times'].pop(filename)
            
        # Remove from processed_files_details
        session_data['processed_files_details'] = [
            f for f in session_data.get('processed_files_details', [])
            if f.get('stored_name') != filename
        ]
            
        session['session_data'] = session_data
        
        return jsonify({
            "status": "success",
            "message": "File cleaned up successfully"
        })
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error cleaning up file {filename}: {e}")
        return jsonify({"status": "error", "message": f"Error cleaning up file: {str(e)}"}), 500

# ----------------- Download All ZIP -----------------
@app.route('/download-all-zip', methods=['POST'])
def download_all_zip():
    """Download all processed files as ZIP (alternative endpoint)"""
    return download_zip() # Directly call the function that returns send_file

# ----------------- Cleanup Session -----------------
@app.route('/cleanup', methods=['POST'])
def cleanup_session():
    """Clean up current session based on type (all or processed)"""
    try:
        data = request.get_json()
        cleanup_type = data.get('type', 'all') # 'all' or 'processed'
        
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({"status": "error", "message": "No active session to clean up."}), 400

        if cleanup_type == 'all':
            manual_clear_session_folders(session_id)
            logger.info(f"{get_session_context()} Manually cleared all session folders for session: {session_id}")
            
            # Reset session data completely
            session.pop('preview_data', None)
            session['session_data'] = SessionData().__dict__ # Re-initialize session data
            
            return jsonify({
                "status": "success",
                "message": "All session data cleared successfully."
            })
        elif cleanup_type == 'processed':
            processed_folder = app.config.get('PROCESSED_FOLDER', DEFAULT_CONFIG['PROCESSED_FOLDER'])
            session_folder_path = get_session_folder(processed_folder)
            
            if os.path.exists(session_folder_path):
                shutil.rmtree(session_folder_path)
                os.makedirs(session_folder_path) # Recreate empty folder
                logger.info(f"{get_session_context()} Cleared processed files for session: {session_id}")
            
            # Clear only processed file tracking in session data
            session_data = session.get('session_data', {})
            session_data['processed_files'] = []
            session_data['file_times'] = {}
            session_data['processed_files_details'] = []
            session['session_data'] = session_data
            
            return jsonify({
                "status": "success",
                "message": "Processed files cleared successfully."
            })
        else:
            return jsonify({"status": "error", "message": "Invalid cleanup type specified."}), 400
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error during cleanup: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error during cleanup: {str(e)}"
        }), 500

# ----------------- Clear Session Route (Legacy) -----------------
# This route is now primarily handled by /cleanup endpoint with type parameter
# Keeping it for backward compatibility if needed, but /cleanup is preferred.
@app.route('/clear', methods=['GET', 'POST'])
def clear_session():
    """Clear session files and data (legacy, use /cleanup POST with type='all')"""
    try:
        session_id = session.get('session_id')
        if session_id:
            manual_clear_session_folders(session_id)
            logger.info(f"{get_session_context()} Manually cleared session folders for session: {session_id}")
        
        session.pop('preview_data', None)
        session['session_data'] = SessionData().__dict__
        
        return jsonify({
            "success": True,
            "message": "Session cleared successfully"
        })
        
    except Exception as e:
        logger.error(f"{get_session_context()} Error clearing session: {e}")
        return jsonify({
            "success": False,
            "message": f"Error clearing session: {str(e)}"
        }), 500

# ----------------- Error Handlers -----------------
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

# ----------------- Main Execution -----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

