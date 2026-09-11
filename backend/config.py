# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ============================================
    # Database Configuration
    # ============================================
    # Use the URL as-is from .env
    # The .env already has the correctly encoded password
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/haji_younas_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # ============================================
    # Security Configuration
    # ============================================
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    JWT_REFRESH_SECRET_KEY = os.getenv('JWT_REFRESH_SECRET_KEY', 'your-super-secret-refresh-key-change-in-production')
    
    # JWT Token Expiry Times
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # Access token expires in 24 hours
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)   # Refresh token expires in 7 days
    
    # Password Reset Token Expiry
    PASSWORD_RESET_TOKEN_EXPIRES = timedelta(hours=1)  # Reset token expires in 1 hour
    
    # ============================================
    # CORS Configuration
    # ============================================
    CORS_ORIGINS = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
         "http://192.168.100.79:3000",
          "http://192.168.10.25:3000",

    ]
    
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_HEADERS = [
        "Content-Type", 
        "Authorization", 
        "Accept", 
        "Origin", 
        "X-Requested-With", 
        "Content-Disposition",
        "X-CSRF-Token"
    ]
    CORS_EXPOSE_HEADERS = [
        "Content-Type", 
        "Authorization",
        "Content-Disposition"
    ]
    CORS_SUPPORTS_CREDENTIALS = True
    CORS_MAX_AGE = 86400  # 24 hours for preflight requests
    
    # ============================================
    # Application Configuration
    # ============================================
    APP_NAME = "Haji Younas Contracting"
    APP_VERSION = "3.0.0"
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # ============================================
    # Email Configuration (for password reset)
    # ============================================
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@hajiyounas.com')
    
    # ============================================
    # Environment Configuration
    # ============================================
    ENV = os.getenv('FLASK_ENV', 'development')
    TESTING = os.getenv('TESTING', 'False').lower() == 'true'
    
    # ============================================
    # Upload Configuration
    # ============================================
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    
    # ============================================
    # Logging Configuration
    # ============================================
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')
    
    # ============================================
    # Rate Limiting (Optional)
    # ============================================
    RATELIMIT_ENABLED = os.getenv('RATELIMIT_ENABLED', 'False').lower() == 'true'
    RATELIMIT_DEFAULT = os.getenv('RATELIMIT_DEFAULT', '100 per hour')
    RATELIMIT_STORAGE_URL = os.getenv('RATELIMIT_STORAGE_URL', 'memory://')
    
    # ============================================
    # Session Configuration
    # ============================================
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # ============================================
    # Security Headers
    # ============================================
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;"
    }
    
    # ============================================
    # Default Admin User Configuration
    # ============================================
    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@hajiyounas.com')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin@123')
    DEFAULT_ADMIN_FULL_NAME = os.getenv('DEFAULT_ADMIN_FULL_NAME', 'System Administrator')
    
    # ============================================
    # Password Policy
    # ============================================
    PASSWORD_MIN_LENGTH = 6
    PASSWORD_REQUIRE_UPPER = True
    PASSWORD_REQUIRE_LOWER = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = False
    
    # ============================================
    # Helper Methods
    # ============================================
    @classmethod
    def get_jwt_config(cls):
        """Get JWT configuration as dictionary"""
        return {
            'secret_key': cls.JWT_SECRET_KEY,
            'refresh_secret_key': cls.JWT_REFRESH_SECRET_KEY,
            'access_expires': cls.JWT_ACCESS_TOKEN_EXPIRES,
            'refresh_expires': cls.JWT_REFRESH_TOKEN_EXPIRES
        }
    
    @classmethod
    def get_cors_config(cls):
        """Get CORS configuration as dictionary"""
        return {
            'origins': cls.CORS_ORIGINS,
            'methods': cls.CORS_METHODS,
            'headers': cls.CORS_HEADERS,
            'expose_headers': cls.CORS_EXPOSE_HEADERS,
            'supports_credentials': cls.CORS_SUPPORTS_CREDENTIALS,
            'max_age': cls.CORS_MAX_AGE
        }
    
    @classmethod
    def is_production(cls):
        """Check if running in production environment"""
        return cls.ENV == 'production'
    
    @classmethod
    def is_development(cls):
        """Check if running in development environment"""
        return cls.ENV == 'development'


# ============================================
# Development Configuration
# ============================================
class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'
    SESSION_COOKIE_SECURE = False
    
    # Override for development
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"]
    
    @classmethod
    def init_app(cls, app):
        print("🚀 Running in Development Mode")


# ============================================
# Production Configuration
# ============================================
class ProductionConfig(Config):
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
    
    # Stricter CORS for production
    CORS_ORIGINS = os.getenv('PROD_CORS_ORIGINS', '').split(',') if os.getenv('PROD_CORS_ORIGINS') else []
    if not CORS_ORIGINS:
        CORS_ORIGINS = ["https://yourdomain.com", "https://app.yourdomain.com"]
    
    @classmethod
    def init_app(cls, app):
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Set up logging
        if not app.debug:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Application startup')


# ============================================
# Testing Configuration
# ============================================
class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    ENV = 'testing'
    
    # Use in-memory database for testing
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    SESSION_COOKIE_SECURE = False
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    @classmethod
    def init_app(cls, app):
        print("🧪 Running in Testing Mode")


# ============================================
# Configuration Factory
# ============================================
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, DevelopmentConfig)


# ============================================
# Environment Variables (.env file)
# ============================================
"""
# .env file example
DATABASE_URL=postgresql://postgres:password@localhost:5432/haji_younas_db
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_REFRESH_SECRET_KEY=your-jwt-refresh-secret-key-here
FLASK_ENV=development
DEBUG=True

# Default Admin
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_EMAIL=admin@hajiyounas.com
DEFAULT_ADMIN_PASSWORD=Admin@123

# Email (for password reset)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Production
PROD_CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
"""