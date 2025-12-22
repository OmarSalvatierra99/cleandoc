"""
CleanDoc - Configuracion de la aplicacion
==========================================
Configuracion centralizada para diferentes entornos.
"""

import os
from typing import Final


class Config:
    """Configuracion base de la aplicacion."""

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    MAX_CONTENT_LENGTH: Final[int] = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: Final[set] = {'.docx'}
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "/tmp/cleandoc_uploads")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5001"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "log/app.log")

    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME: int = 3600


class DevelopmentConfig(Config):
    """Configuracion para desarrollo."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Configuracion para produccion."""
    DEBUG = False


class TestingConfig(Config):
    """Configuracion para testing."""
    TESTING = True
    DEBUG = True


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}


def get_config(config_name: str = None) -> Config:
    """Obtiene la configuracion segun el nombre del entorno."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    return config_by_name.get(config_name, DevelopmentConfig)
