"""
CleanDoc - Aplicación Flask
============================
Factory de la aplicación Flask con configuración de logging,
seguridad y blueprints.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .config import get_config
from .routes import main_bp
from .utils import CleanDocError


def create_app(config_name: str = None) -> Flask:
    """
    Factory para crear y configurar la aplicación Flask.

    Args:
        config_name: Nombre del entorno de configuración

    Returns:
        Aplicación Flask configurada
    """
    # Crear aplicación
    app = Flask(__name__)

    # Cargar configuración
    config = get_config(config_name)
    app.config.from_object(config)

    # Configurar logging
    _setup_logging(app)

    # Registrar blueprints
    app.register_blueprint(main_bp)

    # Configurar headers de seguridad
    _setup_security_headers(app)

    # Configurar manejo de errores
    _setup_error_handlers(app)

    # Crear directorios necesarios
    _create_directories(app)

    app.logger.info(f"CleanDoc iniciado - Entorno: {config_name or 'default'}")

    return app


def _setup_logging(app: Flask) -> None:
    """
    Configura el sistema de logging de la aplicación.

    Args:
        app: Aplicación Flask
    """
    # Obtener nivel de log desde configuración
    log_level_name = app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    # Configurar formato de logs
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Crear directorio de logs si no existe
    log_file = app.config.get('LOG_FILE', 'logs/cleandoc.log')
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Handler para archivo (con rotación)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Configurar logger de Flask
    app.logger.setLevel(log_level)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    app.logger.info(f"Sistema de logging configurado - Nivel: {log_level_name}")


def _setup_security_headers(app: Flask) -> None:
    """
    Configura headers de seguridad HTTP.

    Args:
        app: Aplicación Flask
    """
    @app.after_request
    def add_security_headers(response):
        """Añade headers de seguridad a todas las respuestas"""
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Habilitar protección XSS del navegador
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "script-src 'self' 'unsafe-inline';"
        )

        # Strict Transport Security (solo en producción HTTPS)
        if not app.config.get('DEBUG', False):
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=()'
        )

        return response

    app.logger.info("Headers de seguridad configurados")


def _setup_error_handlers(app: Flask) -> None:
    """
    Configura manejadores de errores globales.

    Args:
        app: Aplicación Flask
    """
    @app.errorhandler(CleanDocError)
    def handle_cleandoc_error(error: CleanDocError):
        """Maneja errores personalizados de CleanDoc"""
        app.logger.warning(f"CleanDocError: {error.message}")
        return jsonify({
            "error": error.message,
            "status": error.status_code
        }), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Maneja excepciones HTTP estándar"""
        app.logger.warning(f"HTTPException: {error.code} - {error.description}")
        return jsonify({
            "error": error.name,
            "message": error.description,
            "status": error.code
        }), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Maneja errores inesperados"""
        app.logger.error(f"Error inesperado: {str(error)}", exc_info=True)
        return jsonify({
            "error": "Error interno del servidor",
            "message": "Ocurrió un error inesperado procesando su solicitud"
        }), 500

    app.logger.info("Manejadores de errores configurados")


def _create_directories(app: Flask) -> None:
    """
    Crea directorios necesarios para la aplicación.

    Args:
        app: Aplicación Flask
    """
    # Directorio de logs
    log_file = app.config.get('LOG_FILE', 'logs/cleandoc.log')
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Directorio de uploads (si se usa)
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        Path(upload_folder).mkdir(parents=True, exist_ok=True)

    app.logger.debug("Directorios creados/verificados")
