# utils/cleanup.py
import os
import shutil
import time
import logging
from flask import current_app
from apscheduler.schedulers.background import BackgroundScheduler

# Set up logger
logger = logging.getLogger(__name__)

# Initialize scheduler (will be configured in main app)
scheduler = BackgroundScheduler()

def get_session_folder_path(base_folder: str, session_id: str) -> str:
    """
    Get the session folder path based on session ID.
    This ensures consistency with how session folders are created in file_manager.py
    """
    return os.path.join(base_folder, f"sess_{session_id}")

def manual_clear_session_folders(session_id: str) -> None:
    """
    Immediately deletes the session's uploads/sess_<id>/, processed/sess_<id>/, 
    and previews/sess_<id>/ folders for the given session.
    
    Args:
        session_id (str): The session ID to clean up
    """
    folders_to_clean = [
        current_app.config.get('UPLOAD_FOLDER', 'uploads'),
        current_app.config.get('PROCESSED_FOLDER', 'processed'),
        current_app.config.get('PREVIEWS_FOLDER', 'previews')
    ]
    
    for base_folder in folders_to_clean:
        session_folder = get_session_folder_path(base_folder, session_id)
        
        if os.path.exists(session_folder) and os.path.isdir(session_folder):
            try:
                # Count files before deletion
                file_count = sum(len(files) for _, _, files in os.walk(session_folder))
                
                # Remove the entire session folder
                shutil.rmtree(session_folder)
                logger.info(f"Manually cleaned up session folder: {session_folder} ({file_count} files)")
                
            except Exception as e:
                logger.error(f"Failed to clean up session folder {session_folder}: {e}")

def _scheduled_cleanup_job(session_id: str) -> None:
    """
    Internal function to perform the actual cleanup.
    Called by the scheduler after the delay.
    """
    logger.info(f"Performing scheduled cleanup for session: {session_id}")
    manual_clear_session_folders(session_id)

def schedule_session_cleanup(session_id: str, delay_seconds: int = 600) -> None:
    """
    Uses APScheduler BackgroundScheduler to schedule deletion of that session's
    folders after the specified delay.
    
    Args:
        session_id (str): The session ID to schedule cleanup for
        delay_seconds (int): Delay in seconds before cleanup (default: 600 = 10 minutes)
    """
    try:
        # Ensure scheduler is running
        if not scheduler.running:
            scheduler.start()
            
        scheduler.add_job(
            _scheduled_cleanup_job,
            'date',
            run_date=time.time() + delay_seconds,
            args=[session_id],
            id=f"cleanup_{session_id}",
            replace_existing=True
        )
        logger.info(f"Scheduled cleanup for session {session_id} in {delay_seconds} seconds")
    except Exception as e:
        logger.error(f"Failed to schedule cleanup for session {session_id}: {e}")

def cleanup_old_sessions(max_age_minutes: int = 10) -> None:
    """
    Iterate over all sess_* folders in uploads/, processed/, and previews/.
    Delete folders older than max_age_minutes.
    
    Args:
        max_age_minutes (int): Maximum age in minutes before folders are deleted (default: 10)
    """
    max_age_seconds = max_age_minutes * 60
    now = time.time()
    folders_checked = 0
    folders_deleted = 0
    
    folders_to_check = [
        current_app.config.get('UPLOAD_FOLDER', 'uploads'),
        current_app.config.get('PROCESSED_FOLDER', 'processed'),
        current_app.config.get('PREVIEWS_FOLDER', 'previews')
    ]
    
    for base_folder in folders_to_check:
        if not os.path.exists(base_folder):
            continue
            
        try:
            for item in os.listdir(base_folder):
                if item.startswith('sess_'):
                    session_folder = os.path.join(base_folder, item)
                    
                    if os.path.isdir(session_folder):
                        folders_checked += 1
                        
                        # Check folder age using creation time or modification time
                        # Use the oldest time between creation and modification
                        try:
                            folder_mtime = os.path.getmtime(session_folder)
                            folder_ctime = os.path.getctime(session_folder)
                            folder_age = now - min(folder_mtime, folder_ctime)
                        except OSError:
                            # If we can't get times, skip this folder
                            continue
                        
                        if folder_age > max_age_seconds:
                            try:
                                # Count files before deletion
                                file_count = sum(len(files) for _, _, files in os.walk(session_folder))
                                
                                # Remove the entire session folder
                                shutil.rmtree(session_folder)
                                folders_deleted += 1
                                logger.info(f"Cleaned up old session folder: {session_folder} (age: {folder_age/60:.1f} minutes, {file_count} files)")
                                
                            except Exception as e:
                                logger.error(f"Failed to clean up old session folder {session_folder}: {e}")
                                
        except Exception as e:
            logger.error(f"Error checking for old sessions in {base_folder}: {e}")
    
    logger.info(f"Global cleanup completed: checked {folders_checked} session folders, deleted {folders_deleted} old folders")

def cleanup_folder(folder_path, max_age_minutes=10, extensions=None):
    """
    Remove files older than max_age_minutes from a folder.
    
    Args:
        folder_path: Path to the folder to clean up
        max_age_minutes: Maximum age in minutes before files are deleted (default: 10)
        extensions: List of file extensions to target (None for all files)
    """
    if not os.path.exists(folder_path):
        logger.warning(f"Cleanup folder does not exist: {folder_path}")
        return 0
    
    now = time.time()
    max_age_seconds = max_age_minutes * 60
    files_deleted = 0
    
    try:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            
            # Skip directories and check file extension
            if not os.path.isfile(file_path):
                continue
                
            if extensions and not any(filename.lower().endswith(ext.lower()) for ext in extensions):
                continue
            
            try:
                file_age = now - os.path.getmtime(file_path)
            except OSError:
                # Skip files we can't get mtime for
                continue
            
            if file_age > max_age_seconds:
                try:
                    os.remove(file_path)
                    files_deleted += 1
                    logger.debug(f"Cleaned up file: {filename} (age: {file_age/60:.1f} minutes)")
                except Exception as e:
                    logger.error(f"Failed to delete {filename}: {e}")
                    
        if files_deleted > 0:
            logger.info(f"Cleaned up {files_deleted} files from {folder_path}")
        return files_deleted
        
    except Exception as e:
        logger.error(f"Error cleaning up folder {folder_path}: {e}")
        return 0

def cleanup_uploaded_files(max_age_minutes=10):
    """Clean up user-uploaded files after specified minutes"""
    try:
        # Use current_app with proper error handling
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        return cleanup_folder(upload_folder, max_age_minutes, extensions=['.pdf'])
    except RuntimeError as e:
        if "working outside of application context" in str(e):
            # Fallback to default folder when outside app context
            return cleanup_folder('uploads', max_age_minutes, extensions=['.pdf'])
        logger.error(f"Error cleaning up uploaded files: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up uploaded files: {e}")
        return 0

def cleanup_processed_files(max_age_minutes=10):
    """Clean up processed files after specified minutes"""
    try:
        processed_folder = current_app.config.get('PROCESSED_FOLDER', 'processed')
        return cleanup_folder(processed_folder, max_age_minutes)
    except RuntimeError as e:
        if "working outside of application context" in str(e):
            return cleanup_folder('processed', max_age_minutes)
        logger.error(f"Error cleaning up processed files: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up processed files: {e}")
        return 0

def cleanup_preview_files(max_age_minutes=10):
    """Clean up preview images after specified minutes"""
    try:
        previews_folder = current_app.config.get('PREVIEWS_FOLDER', 'previews')
        return cleanup_folder(previews_folder, max_age_minutes, extensions=['.jpg', '.jpeg', '.png'])
    except RuntimeError as e:
        if "working outside of application context" in str(e):
            return cleanup_folder('previews', max_age_minutes, extensions=['.jpg', '.jpeg', '.png'])
        logger.error(f"Error cleaning up preview files: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up preview files: {e}")
        return 0

def cleanup_aged_files(upload_max_age_minutes=10, preview_max_age_minutes=10, processed_max_age_minutes=10):
    """
    Clean up all temporary files with configurable retention policies
    
    Args:
        upload_max_age_minutes: Retention for uploaded files (default: 10)
        preview_max_age_minutes: Retention for preview files (default: 10)
        processed_max_age_minutes: Retention for processed files (default: 10)
    """
    total_deleted = 0
    
    total_deleted += cleanup_uploaded_files(upload_max_age_minutes)
    total_deleted += cleanup_preview_files(preview_max_age_minutes)
    total_deleted += cleanup_processed_files(processed_max_age_minutes)
    
    # Also clean up old session folders
    cleanup_old_sessions(max(processed_max_age_minutes, 10))
    
    return total_deleted

def get_folder_size(folder_path):
    """Get total size of folder in MB"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    continue  # Skip files we can't access
        return total_size / (1024 * 1024)  # Convert to MB
    except Exception as e:
        logger.error(f"Error getting folder size for {folder_path}: {e}")
        return 0

def cleanup_if_needed(max_size_mb=1000):
    """
    Emergency cleanup if folders get too large
    """
    try:
        folders_to_check = [
            current_app.config.get('UPLOAD_FOLDER', 'uploads'),
            current_app.config.get('PROCESSED_FOLDER', 'processed'),
            current_app.config.get('PREVIEWS_FOLDER', 'previews')
        ]
    except RuntimeError:
        # Fallback when outside app context
        folders_to_check = ['uploads', 'processed', 'previews']
    
    for folder in folders_to_check:
        if os.path.exists(folder):
            size_mb = get_folder_size(folder)
            if size_mb > max_size_mb:
                logger.warning(f"Folder {folder} exceeds size limit ({size_mb:.1f} MB > {max_size_mb} MB), performing emergency cleanup")
                # Clean files older than 1 minute in emergency
                cleanup_folder(folder, max_age_minutes=1)

# Flask CLI command for manual cleanup
def init_cleanup_cli(app):
    """Initialize Flask CLI commands for cleanup"""
    @app.cli.command("cleanup")
    def cleanup_command():
        """Manual cleanup command"""
        with app.app_context():
            deleted = cleanup_aged_files()
            print(f"Cleaned up {deleted} files")

    @app.cli.command("cleanup-sessions")
    def cleanup_sessions():
        """Clean up old session folders"""
        with app.app_context():
            cleanup_old_sessions()
            print("Session cleanup completed")

    @app.cli.command("cleanup-stats")
    def cleanup_stats():
        """Show cleanup statistics"""
        with app.app_context():
            folders = {
                'Uploads': app.config.get('UPLOAD_FOLDER', 'uploads'),
                'Processed': app.config.get('PROCESSED_FOLDER', 'processed'),
                'Previews': app.config.get('PREVIEWS_FOLDER', 'previews')
            }
            
            for name, path in folders.items():
                if os.path.exists(path):
                    size_mb = get_folder_size(path)
                    file_count = len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
                    print(f"{name}: {file_count} files, {size_mb:.1f} MB")
                else:
                    print(f"{name}: Folder does not exist")

    @app.cli.command("cleanup-emergency")
    def cleanup_emergency():
        """Emergency cleanup for large folders"""
        with app.app_context():
            cleanup_if_needed()
            print("Emergency cleanup completed")

# Start the scheduler when this module is imported
try:
    if not scheduler.running:
        scheduler.start()
        logger.info("Cleanup scheduler started")
except Exception as e:
    logger.error(f"Failed to start cleanup scheduler: {e}")
