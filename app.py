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
    validate_docx_file,
    is_valid_docx_content,
    NoFilesProvidedError,
    InvalidFileError,
    FileProcessingError,
    CleanDocError,
)
from organizar_cedula_resultados_pdf import (  # noqa: E402
    OrganizedPdfFile,
    PdfOrganizationStats,
    organizar_cedulas_resultados_pdf,
    ANEXO_TYPES,
    validar_pdf,
    es_contenido_pdf_valido,
    extraer_texto_pdf,
    extraer_campos,
    normalizar_espacios,
    hash_pdf_stream,
    describir_anexo,
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

    @app.route("/api/health")
    @app.route("/health")  # alias de compatibilidad
    def health_check():
        return jsonify({
            "status": "ok",
            "service": "cleandoc",
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

    @app.route("/organizar_cedula_resultados_pdf", methods=["POST"])
    def organizar_cedula_resultados_pdf_endpoint():
        try:
            files: List[FileStorage] = request.files.getlist("archivo")

            if not files or all(not f.filename for f in files):
                raise NoFilesProvidedError("No se proporcionaron archivos PDF")

            app.logger.info(
                "Recibidos %s PDFs para organizar por sigla y periodo",
                len(files),
            )

            max_size = current_app.config.get('MAX_FILE_SIZE', 50 * 1024 * 1024)
            organized_files, stats = organizar_cedulas_resultados_pdf(
                files,
                max_size=max_size,
            )

            if not organized_files:
                app.logger.warning(
                    "No se pudo organizar ningún PDF válido: %s",
                    "; ".join(stats.errors or stats.duplicate_names or ["sin detalle"]),
                )
                return jsonify(_build_pdf_organization_error_payload(stats)), 400

            app.logger.info(
                "Organización PDF completada - Procesados: %s, Duplicados: %s, Omitidos: %s",
                stats.processed_files,
                stats.duplicates_removed,
                stats.skipped_files,
            )
            if stats.duplicate_names:
                app.logger.warning(
                    "PDFs omitidos por duplicado: %s",
                    "; ".join(stats.duplicate_names),
                )
            if stats.errors:
                app.logger.warning(
                    "Incidencias de organización PDF: %s",
                    "; ".join(stats.errors),
                )

            return _send_organized_pdfs(organized_files, stats)

        except CleanDocError as e:
            app.logger.warning(f"Error de validación PDF: {e.message}")
            return jsonify({"error": e.message}), e.status_code

        except Exception as e:
            app.logger.error(f"Error inesperado: {str(e)}", exc_info=True)
            detail = str(e).strip() or e.__class__.__name__
            return jsonify({
                "error": "Error interno del servidor",
                "message": f"Ocurrió un error organizando los PDFs: {detail}",
                "details": [f"{e.__class__.__name__}: {detail}"],
            }), 500

    @app.route("/contar_cedulas_pdf", methods=["POST"])
    def contar_cedulas_pdf_endpoint():
        try:
            files: List[FileStorage] = request.files.getlist("archivo")

            if not files or all(not f.filename for f in files):
                raise NoFilesProvidedError("No se proporcionaron archivos PDF")

            max_size = current_app.config.get('MAX_FILE_SIZE', 50 * 1024 * 1024)
            result = _count_pdf_stats(files, max_size)

            app.logger.info(
                "Conteo PDF completado - PDFs: %s, Páginas: %s, Observaciones: %s",
                result["total_pdfs"],
                result["total_paginas"],
                result["total_observaciones"],
            )

            return jsonify(result), 200

        except CleanDocError as e:
            app.logger.warning(f"Error de validación PDF: {e.message}")
            return jsonify({"error": e.message}), e.status_code

        except Exception as e:
            app.logger.error(f"Error inesperado: {str(e)}", exc_info=True)
            return jsonify({
                "error": "Error interno del servidor",
                "message": "Ocurrió un error contando los PDFs",
            }), 500


def _count_pdf_stats(
    files: List[FileStorage],
    max_size: int,
) -> dict:
    """Analiza PDFs y devuelve conteo de páginas y observaciones por anexo."""
    hashes: dict = {}
    archivos = []
    por_anexo: dict = {}
    total_paginas = 0
    total_observaciones = 0
    duplicados = 0
    omitidos = 0
    errores = []

    for file in files:
        if not file or not file.filename:
            omitidos += 1
            continue

        try:
            safe_filename = validar_pdf(file, max_size)

            if not es_contenido_pdf_valido(file.stream):
                raise InvalidFileError("El archivo no es un PDF válido")

            texto, page_count = extraer_texto_pdf(file.stream)
            if not texto.strip():
                omitidos += 1
                errores.append(f"{safe_filename}: sin texto extraíble")
                continue

            texto_h = hash_pdf_stream(file.stream)

            if texto_h in hashes:
                duplicados += 1
                continue
            hashes[texto_h] = safe_filename

            campos = extraer_campos(texto, filename=safe_filename)
            anexo = campos["anexo"]
            obs = campos["total_observaciones"]

            total_paginas += page_count
            total_observaciones += obs

            if anexo not in por_anexo:
                por_anexo[anexo] = {
                    "label": describir_anexo(anexo),
                    "pdfs": 0,
                    "paginas": 0,
                    "observaciones": 0,
                }
            por_anexo[anexo]["pdfs"] += 1
            por_anexo[anexo]["paginas"] += page_count
            por_anexo[anexo]["observaciones"] += obs

            archivos.append({
                "nombre": safe_filename,
                "paginas": page_count,
                "observaciones": obs,
                "anexo": anexo,
                "ente": campos["ente_original"],
                "periodo": campos["periodo_original"],
                "fuente": campos["fuente_original"],
            })

        except CleanDocError:
            raise
        except Exception as e:
            omitidos += 1
            errores.append(f"{file.filename}: {str(e)}")

    return {
        "total_pdfs": len(archivos),
        "total_paginas": total_paginas,
        "total_observaciones": total_observaciones,
        "duplicados": duplicados,
        "omitidos": omitidos,
        "por_anexo": por_anexo,
        "archivos": archivos,
        "errores": errores,
    }


def _build_pdf_organization_error_payload(
    stats: PdfOrganizationStats,
    error: str = "No se pudo organizar ningún PDF válido",
) -> dict:
    """Construye una respuesta detallada cuando falla la organización PDF."""
    duplicates = [
        f"{name}: contenido duplicado"
        for name in stats.duplicate_names
    ]
    details = list(stats.errors) + duplicates

    if stats.duplicate_names and not stats.errors:
        message = "Todos los archivos fueron omitidos por duplicado."
    else:
        message = (
            "Todos los archivos fueron omitidos. "
            "Revisa el detalle por archivo para corregir el contenido detectado."
        )

    return {
        "error": error,
        "message": message,
        "details": details,
        "stats": stats.to_dict(),
    }


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


def _send_single_file(
    file_data: Tuple[str, BytesIO],
    stats: CleaningStats,
):
    """Envia un unico archivo DOCX limpio."""
    filename, stream = file_data

    current_app.logger.info(
        f"Enviando archivo único: {filename} - "
        f"Estadísticas: {stats.to_dict()}"
    )

    response = send_file(
        stream,
        as_attachment=True,
        download_name=filename,
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
            for (filename, stream), _stats in zip(files_data, stats_list):
                stream.seek(0)
                zf.writestr(filename, stream.read())

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


def _send_organized_pdfs(
    files_data: List[OrganizedPdfFile],
    stats: PdfOrganizationStats,
):
    """Envía un ZIP con PDFs organizados por sigla y periodo."""
    current_app.logger.info(
        "Creando ZIP de organización PDF con %s archivos",
        len(files_data),
    )

    try:
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in files_data:
                item.stream.seek(0)
                zf.writestr(item.archive_path, item.stream.read())

        zip_buffer.seek(0)

        response = send_file(
            zip_buffer,
            as_attachment=True,
            download_name="cedulas_resultados_organizadas.zip",
            mimetype="application/zip",
        )

        response.headers['X-CleanDoc-Organizer-Total-Files'] = str(stats.total_files)
        response.headers['X-CleanDoc-Organizer-Processed'] = str(stats.processed_files)
        response.headers['X-CleanDoc-Organizer-Duplicates'] = str(stats.duplicates_removed)
        response.headers['X-CleanDoc-Organizer-Skipped'] = str(stats.skipped_files)
        response.headers['X-CleanDoc-Organizer-Folders'] = str(stats.folders_created)
        response.headers['X-CleanDoc-Organizer-Pages'] = str(stats.total_pages)
        response.headers['X-CleanDoc-Organizer-Observations'] = str(stats.total_observations)

        return response
    except Exception as e:
        current_app.logger.error(f"Error creando ZIP de organización PDF: {str(e)}", exc_info=True)
        raise FileProcessingError("Error creando archivo ZIP de organización PDF")


def _format_pdf_organization_summary(stats: PdfOrganizationStats) -> str:
    """Formatea el resumen de organización PDF para incluir en el ZIP."""
    organized_lines = [
        (
            f"  • {item['original_name']} -> {item['archive_path']} "
            f"[ANEXO={item['anexo']}; OBS_REF={','.join(item['observacion_refs']) or 'N/A'}; "
            f"OBS_FINAL={item['total_observaciones']}]"
        )
        for item in stats.organized_items
    ] or ["  • Sin archivos organizados"]

    duplicate_lines = [
        f"  • {name}"
        for name in stats.duplicate_names
    ] or ["  • Sin duplicados detectados"]

    error_lines = [
        f"  • {error}"
        for error in stats.errors
    ] or ["  • Sin errores"]

    return f"""
═══════════════════════════════════════════════════════════════
CleanDoc - Organización de Cédulas de Resultados PDF
═══════════════════════════════════════════════════════════════

Resumen:
─────────────────────────────────────────────────────────────
  • PDFs recibidos: {stats.total_files}
  • PDFs organizados: {stats.processed_files}
  • Duplicados omitidos: {stats.duplicates_removed}
  • PDFs omitidos por error: {stats.skipped_files}
  • Carpetas creadas: {stats.folders_created}
  • Páginas procesadas: {stats.total_pages}
  • Observaciones al final: {stats.total_observations}

Archivos organizados:
─────────────────────────────────────────────────────────────
{chr(10).join(organized_lines)}

Duplicados detectados:
─────────────────────────────────────────────────────────────
{chr(10).join(duplicate_lines)}

Incidencias:
─────────────────────────────────────────────────────────────
{chr(10).join(error_lines)}

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
