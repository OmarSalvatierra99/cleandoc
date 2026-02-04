"""
CleanDoc - Aplicacion Flask
===========================
Punto de entrada unico para la aplicacion CleanDoc.
"""

import logging
import sys
import tempfile
import zipfile
from io import BytesIO
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Tuple

from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify,
    current_app,
)
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException

from config import get_config

SCRIPTS_DIR = Path(__file__).parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from utils import (  # noqa: E402
    get_cleaner,
    CleaningStats,
    PdfScalingStats,
    validate_docx_file,
    validate_pdf_file,
    is_valid_docx_content,
    is_valid_pdf_content,
    scale_pdf_for_print,
    NoFilesProvidedError,
    InvalidFileError,
    FileProcessingError,
    CleanDocError,
)


def create_app(config_name: str = None) -> Flask:
    """Factory para crear y configurar la aplicacion Flask."""
    app = Flask(__name__)

    config = get_config(config_name)
    app.config.from_object(config)

    _setup_logging(app)
    _setup_security_headers(app)
    _setup_error_handlers(app)
    _create_directories(app)
    _register_routes(app)

    app.logger.info(f"CleanDoc iniciado - Entorno: {config_name or 'default'}")

    return app


def _setup_logging(app: Flask) -> None:
    """Configura el sistema de logging de la aplicacion."""
    log_level_name = app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    log_file = app.config.get('LOG_FILE', 'log/app.log')
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    app.logger.setLevel(log_level)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    app.logger.info(f"Sistema de logging configurado - Nivel: {log_level_name}")


def _setup_security_headers(app: Flask) -> None:
    """Configura headers de seguridad HTTP."""

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "script-src 'self' 'unsafe-inline';"
        )

        if not app.config.get('DEBUG', False):
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )

        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response

    app.logger.info("Headers de seguridad configurados")


def _setup_error_handlers(app: Flask) -> None:
    """Configura manejadores de errores globales."""

    @app.errorhandler(CleanDocError)
    def handle_cleandoc_error(error: CleanDocError):
        app.logger.warning(f"CleanDocError: {error.message}")
        return jsonify({
            "error": error.message,
            "status": error.status_code,
        }), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        app.logger.warning(f"HTTPException: {error.code} - {error.description}")
        return jsonify({
            "error": error.name,
            "message": error.description,
            "status": error.code,
        }), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.error(f"Error inesperado: {str(error)}", exc_info=True)
        return jsonify({
            "error": "Error interno del servidor",
            "message": "Ocurrió un error inesperado procesando su solicitud",
        }), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        max_total_mb = app.config.get("MAX_CONTENT_LENGTH", 0) / (1024 * 1024)
        app.logger.warning("Intento de subir carga total demasiado grande")
        return jsonify({
            "error": "Carga demasiado grande",
            "message": (
                "La carga total excede el tamaño máximo permitido "
                f"de {max_total_mb:.0f} MB"
            ),
        }), 413

    app.logger.info("Manejadores de errores configurados")


def _create_directories(app: Flask) -> None:
    """Crea directorios necesarios para la aplicacion."""
    log_file = app.config.get('LOG_FILE', 'log/app.log')
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        Path(upload_folder).mkdir(parents=True, exist_ok=True)

    app.logger.debug("Directorios creados/verificados")


def _register_routes(app: Flask) -> None:
    """Registra rutas principales de la aplicacion."""

    @app.route("/")
    def index():
        app.logger.info("Acceso a pagina principal")
        return render_template("index.html")

    @app.route("/health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "CleanDoc",
            "version": "2.0.0",
        }), 200

    @app.route("/limpiar_cedula", methods=["POST"])
    def limpiar_endpoint():
        try:
            files: List[FileStorage] = request.files.getlist("archivo")

            if not files or all(not f.filename for f in files):
                raise NoFilesProvidedError()

            app.logger.info(f"Recibidos {len(files)} archivos para procesar")

            cleaned_files, stats_list = _process_files(files)

            if not cleaned_files:
                raise InvalidFileError("No se pudieron procesar archivos válidos")

            if len(cleaned_files) == 1:
                return _send_single_file(cleaned_files[0], stats_list[0])
            return _send_multiple_files(cleaned_files, stats_list)

        except CleanDocError as e:
            app.logger.warning(f"Error de validación: {e.message}")
            return jsonify({"error": e.message}), e.status_code

        except Exception as e:
            app.logger.error(f"Error inesperado: {str(e)}", exc_info=True)
            return jsonify({
                "error": "Error interno del servidor",
                "message": "Ocurrió un error procesando los archivos",
            }), 500

    @app.route("/escalar_cedula_pdf", methods=["POST"])
    def escalar_pdf_endpoint():
        try:
            files: List[FileStorage] = request.files.getlist("archivo")

            if not files or all(not f.filename for f in files):
                raise NoFilesProvidedError("No se proporcionaron archivos PDF")

            app.logger.info(f"Recibidos {len(files)} PDFs para escalar")

            scaled_files, stats_list = _process_pdf_files(files)

            if not scaled_files:
                raise InvalidFileError("No se pudieron procesar PDFs válidos")

            if len(scaled_files) == 1:
                return _send_single_pdf(scaled_files[0], stats_list[0])
            return _send_multiple_pdfs(scaled_files, stats_list)

        except CleanDocError as e:
            app.logger.warning(f"Error de validación PDF: {e.message}")
            return jsonify({"error": e.message}), e.status_code

        except Exception as e:
            app.logger.error(f"Error inesperado: {str(e)}", exc_info=True)
            return jsonify({
                "error": "Error interno del servidor",
                "message": "Ocurrió un error procesando los PDFs",
            }), 500


def _process_files(
    files: List[FileStorage],
) -> Tuple[List[Tuple[str, BytesIO]], List[CleaningStats]]:
    """Procesa multiples archivos DOCX."""
    cleaner = get_cleaner()
    cleaned_files = []
    stats_list = []
    max_size = current_app.config.get('MAX_FILE_SIZE', 50 * 1024 * 1024)

    for file in files:
        if not file or not file.filename:
            current_app.logger.warning("Archivo vacío recibido, omitiendo")
            continue

        try:
            safe_filename, _ = validate_docx_file(file, max_size)

            if not is_valid_docx_content(file.stream):
                current_app.logger.warning(
                    f"Archivo '{safe_filename}' no es un DOCX válido, omitiendo"
                )
                continue

            file.stream.seek(0)
            cleaned_stream, stats = cleaner.clean_document(file.stream, safe_filename)

            cleaned_files.append((safe_filename, cleaned_stream))
            stats_list.append(stats)

            current_app.logger.info(
                f"Archivo '{safe_filename}' procesado exitosamente - "
                f"Estadísticas: {stats.to_dict()}"
            )

        except CleanDocError:
            raise

        except Exception as e:
            error_msg = f"Error procesando '{file.filename}': {str(e)}"
            current_app.logger.error(error_msg, exc_info=True)
            continue

    return cleaned_files, stats_list


def _process_pdf_files(
    files: List[FileStorage],
) -> Tuple[List[Tuple[str, BytesIO]], List[PdfScalingStats]]:
    """Procesa multiples archivos PDF y los escala para impresión."""
    scaled_files = []
    stats_list = []
    max_size = current_app.config.get('MAX_FILE_SIZE', 50 * 1024 * 1024)

    for file in files:
        if not file or not file.filename:
            current_app.logger.warning("PDF vacío recibido, omitiendo")
            continue

        try:
            safe_filename, _ = validate_pdf_file(file, max_size)

            if not is_valid_pdf_content(file.stream):
                current_app.logger.warning(
                    f"Archivo '{safe_filename}' no es un PDF válido, omitiendo"
                )
                continue

            file.stream.seek(0)
            scaled_stream, stats = scale_pdf_for_print(file.stream)

            scaled_files.append((safe_filename, scaled_stream))
            stats_list.append(stats)

            current_app.logger.info(
                f"PDF '{safe_filename}' escalado exitosamente - "
                f"Estadísticas: {stats.to_dict()}"
            )

        except CleanDocError:
            raise

        except Exception as e:
            error_msg = f"Error procesando '{file.filename}': {str(e)}"
            current_app.logger.error(error_msg, exc_info=True)
            continue

    return scaled_files, stats_list


def _send_single_file(
    file_data: Tuple[str, BytesIO],
    stats: CleaningStats,
):
    """Envia un unico archivo DOCX limpio."""
    filename, stream = file_data

    current_app.logger.info(
        f"Enviando archivo único: limpia_{filename} - "
        f"Estadísticas: {stats.to_dict()}"
    )

    response = send_file(
        stream,
        as_attachment=True,
        download_name=f"limpia_{filename}",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    response.headers['X-CleanDoc-Images-Removed'] = str(stats.images_removed)
    response.headers['X-CleanDoc-Paragraphs-Cleaned'] = str(stats.institutional_paragraphs_cleaned)
    response.headers['X-CleanDoc-Signature-Removed'] = str(stats.signature_section_removed)

    return response


def _send_multiple_files(
    files_data: List[Tuple[str, BytesIO]],
    stats_list: List[CleaningStats],
):
    """Envia multiples archivos DOCX limpios en un ZIP."""
    current_app.logger.info(f"Creando archivo ZIP con {len(files_data)} archivos")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for (filename, stream), stats in zip(files_data, stats_list):
                zf.writestr(f"limpia_{filename}", stream.read())

                stats_filename = f"limpia_{filename}_stats.txt"
                stats_content = _format_stats(filename, stats)
                zf.writestr(stats_filename, stats_content)

        tmp.seek(0)

        response = send_file(
            tmp.name,
            as_attachment=True,
            download_name="cleandoc_limpios.zip",
            mimetype="application/zip",
        )

        total_images = sum(s.images_removed for s in stats_list)
        total_paragraphs = sum(s.institutional_paragraphs_cleaned for s in stats_list)

        response.headers['X-CleanDoc-Total-Files'] = str(len(files_data))
        response.headers['X-CleanDoc-Total-Images-Removed'] = str(total_images)
        response.headers['X-CleanDoc-Total-Paragraphs-Cleaned'] = str(total_paragraphs)

        current_app.logger.info(
            "ZIP creado exitosamente - "
            f"Archivos: {len(files_data)}, "
            f"Imágenes eliminadas: {total_images}, "
            f"Párrafos limpiados: {total_paragraphs}"
        )

        return response

    except Exception as e:
        current_app.logger.error(f"Error creando archivo ZIP: {str(e)}", exc_info=True)
        raise FileProcessingError("Error creando archivo ZIP")


def _send_single_pdf(
    file_data: Tuple[str, BytesIO],
    stats: PdfScalingStats,
):
    """Envia un unico PDF escalado."""
    filename, stream = file_data

    current_app.logger.info(
        f"Enviando PDF único: escalado_{filename} - "
        f"Estadísticas: {stats.to_dict()}"
    )

    response = send_file(
        stream,
        as_attachment=True,
        download_name=f"escalado_{filename}",
        mimetype="application/pdf",
    )

    response.headers['X-CleanDoc-Pdf-Total-Pages'] = str(stats.total_pages)
    response.headers['X-CleanDoc-Pdf-Adjusted-Pages'] = str(stats.adjusted_pages)

    return response


def _send_multiple_pdfs(
    files_data: List[Tuple[str, BytesIO]],
    stats_list: List[PdfScalingStats],
):
    """Envia multiples PDFs escalados en un ZIP."""
    current_app.logger.info(f"Creando ZIP con {len(files_data)} PDFs escalados")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for (filename, stream), stats in zip(files_data, stats_list):
                zf.writestr(f"escalado_{filename}", stream.read())

                stats_filename = f"escalado_{filename}_stats.txt"
                stats_content = _format_pdf_stats(filename, stats)
                zf.writestr(stats_filename, stats_content)

        tmp.seek(0)

        response = send_file(
            tmp.name,
            as_attachment=True,
            download_name="cedulas_escaladas.zip",
            mimetype="application/zip",
        )

        total_pages = sum(s.total_pages for s in stats_list)
        total_adjusted = sum(s.adjusted_pages for s in stats_list)

        response.headers['X-CleanDoc-Pdf-Total-Files'] = str(len(files_data))
        response.headers['X-CleanDoc-Pdf-Total-Pages'] = str(total_pages)
        response.headers['X-CleanDoc-Pdf-Adjusted-Pages'] = str(total_adjusted)

        current_app.logger.info(
            "ZIP PDF creado exitosamente - "
            f"Archivos: {len(files_data)}, "
            f"Páginas: {total_pages}, "
            f"Páginas ajustadas: {total_adjusted}"
        )

        return response

    except Exception as e:
        current_app.logger.error(f"Error creando ZIP de PDFs: {str(e)}", exc_info=True)
        raise FileProcessingError("Error creando archivo ZIP de PDFs")


def _format_stats(filename: str, stats: CleaningStats) -> str:
    """Formatea las estadisticas de limpieza para incluir en el ZIP."""
    return f"""
═══════════════════════════════════════════════════════════════
CleanDoc - Estadísticas de Limpieza
═══════════════════════════════════════════════════════════════

Archivo: {filename}

Elementos eliminados/limpiados:
─────────────────────────────────────────────────────────────
  • Imágenes de encabezados eliminadas: {stats.images_removed}
  • Párrafos institucionales limpiados: {stats.institutional_paragraphs_cleaned}
  • Textboxes limpiados: {stats.textboxes_cleaned}
  • Sección de firmas eliminada: {'Sí' if stats.signature_section_removed else 'No'}
  • Total de párrafos eliminados: {stats.paragraphs_removed}

Estado: {'Completado con advertencias' if stats.errors else 'Completado exitosamente'}
{f'Errores: {len(stats.errors)}' if stats.errors else ''}

═══════════════════════════════════════════════════════════════
© Órgano de Fiscalización Superior del Estado de Tlaxcala
Sistema CleanDoc v2.0
═══════════════════════════════════════════════════════════════
""".strip()


def _format_pdf_stats(filename: str, stats: PdfScalingStats) -> str:
    """Formatea las estadisticas de escalado para incluir en el ZIP."""
    return f"""
═══════════════════════════════════════════════════════════════
CleanDoc - Estadísticas de Escalado PDF
═══════════════════════════════════════════════════════════════

Archivo: {filename}

Resumen:
─────────────────────────────────────────────────────────────
  • Páginas totales: {stats.total_pages}
  • Páginas ajustadas: {stats.adjusted_pages}

Notas:
  • El contenido se centra y se escala sin recortar información.
  • Tamaño de salida: Carta (8.5 x 11 in).

═══════════════════════════════════════════════════════════════
© Órgano de Fiscalización Superior del Estado de Tlaxcala
Sistema CleanDoc v2.0
═══════════════════════════════════════════════════════════════
""".strip()


app = create_app()


if __name__ == "__main__":
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 4085)
    debug = app.config.get('DEBUG', False)
    env = app.config.get('ENV', 'development')

    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                      CleanDoc v2.0                            ║
    ║        Órgano de Fiscalización Superior de Tlaxcala          ║
    ╚═══════════════════════════════════════════════════════════════╝

    🚀 Servidor iniciando...
    📍 Host: {host}
    🔌 Puerto: {port}
    🌍 Entorno: {env}
    🔧 Debug: {debug}

    ═══════════════════════════════════════════════════════════════
    """)

    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n\n👋 Servidor detenido por el usuario\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error iniciando servidor: {str(e)}\n")
        sys.exit(1)
