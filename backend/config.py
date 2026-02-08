"""Configuration management for production deployment"""

import os
from pathlib import Path

class Config:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    
    # Model configuration
    SEQUENCE_LENGTH = 30
    FEATURE_DIM = 126
    CONFIDENCE_THRESHOLD = 0.25
    MIN_HAND_CONFIDENCE = 0.6
    
    # Paths
    BASE_DIR = Path(__file__).parent
    MODELS_DIR = BASE_DIR / 'models'
    ARTIFACTS_DIR = BASE_DIR / 'artifacts'
    VIDEOS_DIR = BASE_DIR / 'data' / 'videos'
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = BASE_DIR / 'logs' / 'app.log'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'production')
    
    if env == 'development':
        return DevelopmentConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return ProductionConfig()