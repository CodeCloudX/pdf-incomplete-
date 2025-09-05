# utils/file_manager.py
import os
import uuid
import logging
from flask import session, current_app

# Set up logger
logger = logging.getLogger(__name__)

def ensure_session_id() -> str:
    """
    Get or create a session ID for the current user.
    Returns a UUID4 string stored in Flask session.
    """
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        logger.info(f"Generated new session ID: {session['session_id']}")
    
    return session['session_id']

def get_session_folder(base_folder: str) -> str:
    """
    Ensure a subfolder sess_<session_id> exists inside the given base_folder.
    Returns the absolute path to that folder.
    
    Args:
        base_folder (str): Base folder path (uploads, processed, or previews)
        
    Returns:
        str: Absolute path to session-specific folder
    """
    session_id = ensure_session_id()
    session_folder = os.path.join(base_folder, f"sess_{session_id}")
    
    try:
        os.makedirs(session_folder, exist_ok=True)
        logger.debug(f"Session folder ensured: {session_folder}")
        return os.path.abspath(session_folder)
    except Exception as e:
        logger.error(f"Failed to create session folder {session_folder}: {e}")
        raise RuntimeError(f"Could not create session folder: {e}")

def get_session_upload_folder() -> str:
    """Get session-specific upload folder path"""
    return get_session_folder(current_app.config.get('UPLOAD_FOLDER', 'uploads'))

def get_session_processed_folder() -> str:
    """Get session-specific processed folder path"""
    return get_session_folder(current_app.config.get('PROCESSED_FOLDER', 'processed'))

def get_session_previews_folder() -> str:
    """Get session-specific previews folder path"""
    return get_session_folder(current_app.config.get('PREVIEWS_FOLDER', 'previews'))
