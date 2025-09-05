# config.py
import os
from datetime import timedelta

class Config:
    # 🔑 Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 📂 Base directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # 🚦 Debug mode
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # 🌐 Server settings
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # 📁 Folder paths (relative to BASE_DIR)
    UPLOAD_FOLDER = 'uploads'
    PROCESSED_FOLDER = 'processed'
    PREVIEWS_FOLDER = 'previews'
    CACHE_FOLDER = 'cache'
    
    # 📏 File size limits (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # Flask request limit
    
    # 🔹 Allowed file extensions
    ALLOWED_EXTENSIONS = {'pdf'}
    
    # ⏰ Session settings - CORRECTED TO 10 MINUTES
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=10)
    
    # ⚙️ Tool settings
    MAX_CONCURRENT_PROCESSES = 4
    
    # 🧹 Cleanup settings (minutes) - 10 MINUTES MATCHING SESSION
    UPLOAD_FILE_RETENTION = 10      # 10 minutes for uploads
    PREVIEW_FILE_RETENTION = 10     # 10 minutes for previews  
    PROCESSED_FILE_RETENTION = 10   # 10 minutes for processed files
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with configuration"""
        # Create necessary directories
        folders = [
            cls.UPLOAD_FOLDER,
            cls.PROCESSED_FOLDER, 
            cls.PREVIEWS_FOLDER,
            cls.CACHE_FOLDER
        ]
        
        for folder in folders:
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception as e:
                raise RuntimeError(f"Failed to create folder {folder}: {str(e)}")
        
        # Set app configuration
        app.config['MAX_CONTENT_LENGTH'] = cls.MAX_CONTENT_LENGTH
        app.config['UPLOAD_FOLDER'] = cls.get_absolute_path(cls.UPLOAD_FOLDER)
        app.config['PROCESSED_FOLDER'] = cls.get_absolute_path(cls.PROCESSED_FOLDER)
        app.config['PREVIEWS_FOLDER'] = cls.get_absolute_path(cls.PREVIEWS_FOLDER)
        app.config['CACHE_FOLDER'] = cls.get_absolute_path(cls.CACHE_FOLDER)
        app.config['ALLOWED_EXTENSIONS'] = cls.ALLOWED_EXTENSIONS
        app.config['SECRET_KEY'] = cls.SECRET_KEY
        app.config['DEBUG'] = cls.DEBUG
        
        # Set session lifetime
        app.config['PERMANENT_SESSION_LIFETIME'] = cls.PERMANENT_SESSION_LIFETIME
        
        # Set cleanup retention times
        app.config['UPLOAD_RETENTION_MINUTES'] = cls.UPLOAD_FILE_RETENTION
        app.config['PREVIEW_RETENTION_MINUTES'] = cls.PREVIEW_FILE_RETENTION
        app.config['PROCESSED_RETENTION_MINUTES'] = cls.PROCESSED_FILE_RETENTION
    
    @classmethod
    def get_absolute_path(cls, relative_path):
        """Get absolute path for a relative path from BASE_DIR"""
        return os.path.join(cls.BASE_DIR, relative_path)
    
    @classmethod
    def get_upload_path(cls):
        """Get absolute upload folder path"""
        return cls.get_absolute_path(cls.UPLOAD_FOLDER)
    
    @classmethod
    def get_processed_path(cls):
        """Get absolute processed folder path"""
        return cls.get_absolute_path(cls.PROCESSED_FOLDER)
    
    @classmethod
    def get_previews_path(cls):
        """Get absolute previews folder path"""
        return cls.get_absolute_path(cls.PREVIEWS_FOLDER)
    
    @classmethod
    def get_cache_path(cls):
        """Get absolute cache folder path"""
        return cls.get_absolute_path(cls.CACHE_FOLDER)
