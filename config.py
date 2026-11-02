"""
Configuration classes for Tshienda Sneaker Care web application.
Supports local SQLite development and seamless migration to PostgreSQL in production.
"""
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tshienda-dev-secret-key-uwc-2026-secure-random')
    
    # Database configuration (PostgreSQL compatible, defaults to SQLite)
    db_url = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(basedir, 'instance', 'tshienda.db')}")
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session & Cookie Security
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV', 'development') == 'production'
    WTF_CSRF_ENABLED = True
    
    # Staff Security & Lockout Policy
    MAX_FAILED_LOGINS = int(os.environ.get('MAX_FAILED_LOGINS', 5))
    LOCKOUT_DURATION_MINUTES = int(os.environ.get('LOCKOUT_DURATION_MINUTES', 15))
    
    # Rate Limiting (sliding window requests per minute)
    RATE_LIMIT_LOGIN_PER_MINUTE = int(os.environ.get('RATE_LIMIT_LOGIN_PER_MINUTE', 5))
    RATE_LIMIT_TRACK_PER_MINUTE = int(os.environ.get('RATE_LIMIT_TRACK_PER_MINUTE', 15))
    
    # POPIA Data Retention
    POPIA_PHONE_RETENTION_MONTHS = int(os.environ.get('POPIA_PHONE_RETENTION_MONTHS', 12))
    
    # WhatsApp Phase 2 Cloud API Feature Flag (Disabled by default)
    WHATSAPP_CLOUD_API_ENABLED = os.environ.get('WHATSAPP_CLOUD_API_ENABLED', 'false').strip().lower() in ('true', '1', 'yes')
    WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.environ.get('WHATSAPP_WEBHOOK_VERIFY_TOKEN', '')
    WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID', '')
    
    # Campus Details
    CAMPUS_NAME = "University of the Western Cape (UWC)"
    LOCATION_NOTE = "Student Centre Kiosk, Robert Sobukwe Rd, Bellville, Cape Town"
    OFFICIAL_CONTACT_PHONE = "+27 82 000 0000"

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'test_tshienda.db')}"
    SESSION_COOKIE_SECURE = False
    RATE_LIMIT_LOGIN_PER_MINUTE = 1000
    RATE_LIMIT_TRACK_PER_MINUTE = 1000

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
