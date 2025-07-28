"""
Application configuration
"""
import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-to-a-random-secret')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///sentinelzero.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Pushover configuration
    PUSHOVER_API_TOKEN = os.environ.get('PUSHOVER_API_TOKEN')
    PUSHOVER_USER_KEY = os.environ.get('PUSHOVER_USER_KEY')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
