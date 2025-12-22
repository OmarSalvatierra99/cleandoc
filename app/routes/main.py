"""
CleanDoc - Rutas principales
=============================
Define las rutas y endpoints de la aplicación.
"""

import logging
import tempfile
import zipfile
from typing import List, Tuple
from io import BytesIO

from flask import (
    Blueprint,
    render_template,
    request,
    send_file,
    jsonify,
    current_app
)
from werkzeug.datastructures import FileStorage

from ..services import get_cleaner, CleaningStats
from ..utils import (
    validate_docx_file,
    is_valid_docx_content,
    NoFilesProvidedError,
    InvalidFileError,
    FileProcessingError,
    CleanDocError
)

# Configurar logger
logger = logging.getLogger(__name__)

# Crear blueprint
main_bp = Blueprint('main', __name__)


@main_bp.route("/")
def index():
    """
    Página principal de la aplicación.

    Returns:
        Template HTML renderizado
    """
    logger.info("Acceso a página principal")
    return render_template("index.html")


@main_bp.route("/health")
def health_check():
    """
    Endpoint de health check para monitoreo.

    Returns:
        JSON con estado de la aplicación
    """
    return jsonify({
        "status": "healthy",
        "service": "CleanDoc",
        "version": "2.0.0"
    }), 200


@main_bp.route("/limpiar_cedula", methods=["POST"])
def limpiar_endpoint():
    """
    Endpoint para limpiar documentos DOCX.

    Acepta uno o múltiples archivos DOCX y retorna:
    - Un archivo DOCX limpio (si se envía 1 archivo)
    - Un archivo ZIP con todos los archivos limpios (si se envían múltiples)

    Returns:
        Archivo DOCX o ZIP con documentos limpios

    Raises:
        400: Si no se envían archivos o son inválidos
        413: Si algún archivo excede el tamaño máximo
        415: Si el tipo de archivo no está soportado
        500: Si hay un error procesando los archivos
    """
    try:
        # Obtener archivos del request
        files: List[FileStorage] = request.files.getlist("archivo")

        if not files or all(not f.filename for f in files):
            raise NoFilesProvidedError()

        logger.info(f"Recibidos {len(files)} archivos para procesar")

        # Procesar archivos
        cleaned_files, stats_list = _process_files(files)

        if not cleaned_files:
            raise InvalidFileError("No se pudieron procesar archivos válidos")

        # Retornar resultado
        if len(cleaned_files) == 1:
            return _send_single_file(cleaned_files[0], stats_list[0])
        else:
            return _send_multiple_files(cleaned_files, stats_list)

    except CleanDocError as e:
        logger.warning(f"Error de validación: {e.message}")
        return jsonify({"error": e.message}), e.status_code

    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Error interno del servidor",
            "message": "Ocurrió un error procesando los archivos"
        }), 500


def _process_files(
    files: List[FileStorage]
) -> Tuple[List[Tuple[str, BytesIO]], List[CleaningStats]]:
    """
    Procesa múltiples archivos DOCX.

    Args:
        files: Lista de archivos a procesar

    Returns:
        Tupla con (archivos_limpios, estadísticas)
    """
    cleaner = get_cleaner()
    cleaned_files = []
    stats_list = []
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024)

    for file in files:
        if not file or not file.filename:
            logger.warning("Archivo vacío recibido, omitiendo")
            continue

        try:
            # Validar archivo
            safe_filename, _ = validate_docx_file(file, max_size)

            # Validar contenido del archivo
            if not is_valid_docx_content(file.stream):
                logger.warning(f"Archivo '{safe_filename}' no es un DOCX válido, omitiendo")
                continue

            # Limpiar documento
            file.stream.seek(0)
            cleaned_stream, stats = cleaner.clean_document(file.stream, safe_filename)

            cleaned_files.append((safe_filename, cleaned_stream))
            stats_list.append(stats)

            logger.info(
                f"Archivo '{safe_filename}' procesado exitosamente - "
                f"Estadísticas: {stats.to_dict()}"
            )

        except CleanDocError as e:
            # Re-lanzar errores de validación
            raise

        except Exception as e:
            error_msg = f"Error procesando '{file.filename}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Continuar con los demás archivos en caso de error
            continue

    return cleaned_files, stats_list


def _send_single_file(
    file_data: Tuple[str, BytesIO],
    stats: CleaningStats
) -> send_file:
    """
    Envía un único archivo DOCX limpio.

    Args:
        file_data: Tupla con (nombre, stream)
        stats: Estadísticas de limpieza

    Returns:
        Respuesta Flask con el archivo
    """
    filename, stream = file_data

    logger.info(
        f"Enviando archivo único: limpia_{filename} - "
        f"Estadísticas: {stats.to_dict()}"
    )

    response = send_file(
        stream,
        as_attachment=True,
        download_name=f"limpia_{filename}",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    # Añadir headers personalizados con estadísticas
    response.headers['X-CleanDoc-Images-Removed'] = str(stats.images_removed)
    response.headers['X-CleanDoc-Paragraphs-Cleaned'] = str(stats.institutional_paragraphs_cleaned)
    response.headers['X-CleanDoc-Signature-Removed'] = str(stats.signature_section_removed)

    return response


def _send_multiple_files(
    files_data: List[Tuple[str, BytesIO]],
    stats_list: List[CleaningStats]
) -> send_file:
    """
    Envía múltiples archivos DOCX limpios en un ZIP.

    Args:
        files_data: Lista de tuplas con (nombre, stream)
        stats_list: Lista de estadísticas de limpieza

    Returns:
        Respuesta Flask con el archivo ZIP
    """
    logger.info(f"Creando archivo ZIP con {len(files_data)} archivos")

    # Crear archivo temporal para el ZIP
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for (filename, stream), stats in zip(files_data, stats_list):
                # Añadir archivo al ZIP
                zf.writestr(f"limpia_{filename}", stream.read())

                # Añadir archivo de estadísticas
                stats_filename = f"limpia_{filename}_stats.txt"
                stats_content = _format_stats(filename, stats)
                zf.writestr(stats_filename, stats_content)

        tmp.seek(0)

        response = send_file(
            tmp.name,
            as_attachment=True,
            download_name="cleandoc_limpios.zip",
            mimetype="application/zip"
        )

        # Calcular estadísticas totales
        total_images = sum(s.images_removed for s in stats_list)
        total_paragraphs = sum(s.institutional_paragraphs_cleaned for s in stats_list)

        response.headers['X-CleanDoc-Total-Files'] = str(len(files_data))
        response.headers['X-CleanDoc-Total-Images-Removed'] = str(total_images)
        response.headers['X-CleanDoc-Total-Paragraphs-Cleaned'] = str(total_paragraphs)

        logger.info(
            f"ZIP creado exitosamente - "
            f"Archivos: {len(files_data)}, "
            f"Imágenes eliminadas: {total_images}, "
            f"Párrafos limpiados: {total_paragraphs}"
        )

        return response

    except Exception as e:
        logger.error(f"Error creando archivo ZIP: {str(e)}", exc_info=True)
        raise FileProcessingError("Error creando archivo ZIP")


def _format_stats(filename: str, stats: CleaningStats) -> str:
    """
    Formatea las estadísticas de limpieza para incluir en el ZIP.

    Args:
        filename: Nombre del archivo
        stats: Estadísticas de limpieza

    Returns:
        Texto formateado con las estadísticas
    """
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


@main_bp.errorhandler(413)
def request_entity_too_large(error):
    """
    Maneja errores de archivos demasiado grandes.

    Args:
        error: Error HTTP 413

    Returns:
        JSON con mensaje de error
    """
    logger.warning("Intento de subir archivo demasiado grande")
    return jsonify({
        "error": "Archivo demasiado grande",
        "message": "El archivo excede el tamaño máximo permitido de 50 MB"
    }), 413


@main_bp.errorhandler(500)
def internal_server_error(error):
    """
    Maneja errores internos del servidor.

    Args:
        error: Error HTTP 500

    Returns:
        JSON con mensaje de error
    """
    logger.error(f"Error interno del servidor: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Ocurrió un error procesando su solicitud"
    }), 500
