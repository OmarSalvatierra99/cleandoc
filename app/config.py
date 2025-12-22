"""
CleanDoc - Configuración de la aplicación
===========================================
Configuración centralizada para diferentes entornos.
"""

import os
from typing import Final


class Config:
    """Configuración base de la aplicación"""

    # Configuración de Flask
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # Configuración de archivos
    MAX_CONTENT_LENGTH: Final[int] = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: Final[set] = {'.docx'}
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "/tmp/cleandoc_uploads")

    # Configuración de servidor
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "4085"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Configuración de logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/cleandoc.log")

    # Configuración de seguridad
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME: int = 3600  # 1 hora


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    DEBUG = True


# Mapeo de configuraciones
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: str = None) -> Config:
    """
    Obtiene la configuración según el nombre del entorno.

    Args:
        config_name: Nombre del entorno (development, production, testing)

    Returns:
        Instancia de configuración correspondiente
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    return config_by_name.get(config_name, DevelopmentConfig)
