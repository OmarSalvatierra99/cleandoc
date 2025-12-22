"""
CleanDoc - Validadores
======================
Funciones de validación de archivos y datos.
"""

import os
import re
from pathlib import Path
from typing import Optional
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .exceptions import (
    InvalidFileError,
    UnsupportedFileTypeError,
    FileTooLargeError
)


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza el nombre del archivo para prevenir ataques de path traversal.

    Args:
        filename: Nombre del archivo original

    Returns:
        Nombre del archivo sanitizado

    Raises:
        InvalidFileError: Si el nombre del archivo no es válido
    """
    if not filename:
        raise InvalidFileError("El nombre del archivo está vacío")

    # Usar secure_filename de werkzeug
    safe_name = secure_filename(filename)

    if not safe_name:
        raise InvalidFileError(f"Nombre de archivo inválido: {filename}")

    # Validar que solo contenga caracteres seguros
    if not re.match(r'^[\w\-. ]+$', safe_name):
        raise InvalidFileError(f"Nombre de archivo contiene caracteres no permitidos: {filename}")

    return safe_name


def validate_file_extension(filename: str, allowed_extensions: set = {'.docx'}) -> bool:
    """
    Valida que el archivo tenga una extensión permitida.

    Args:
        filename: Nombre del archivo
        allowed_extensions: Set de extensiones permitidas

    Returns:
        True si la extensión es válida

    Raises:
        UnsupportedFileTypeError: Si la extensión no está permitida
    """
    if not filename:
        raise InvalidFileError("El nombre del archivo está vacío")

    file_ext = Path(filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise UnsupportedFileTypeError(
            f"Extensión '{file_ext}' no permitida. Solo se permiten: {', '.join(allowed_extensions)}"
        )

    return True


def validate_file_size(file: FileStorage, max_size: int = 50 * 1024 * 1024) -> bool:
    """
    Valida que el archivo no exceda el tamaño máximo.

    Args:
        file: Objeto FileStorage
        max_size: Tamaño máximo en bytes (default: 50 MB)

    Returns:
        True si el tamaño es válido

    Raises:
        FileTooLargeError: Si el archivo excede el tamaño máximo
    """
    if file is None:
        raise InvalidFileError("El archivo es None")

    # Obtener el tamaño del archivo
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        current_size_mb = size / (1024 * 1024)
        raise FileTooLargeError(
            f"El archivo ({current_size_mb:.2f} MB) excede el tamaño máximo permitido ({max_size_mb:.2f} MB)"
        )

    return True


def validate_docx_file(file: FileStorage, max_size: int = 50 * 1024 * 1024) -> tuple[str, bool]:
    """
    Valida completamente un archivo DOCX.

    Args:
        file: Objeto FileStorage
        max_size: Tamaño máximo permitido en bytes

    Returns:
        Tupla con (nombre_sanitizado, es_válido)

    Raises:
        InvalidFileError: Si el archivo no es válido
        UnsupportedFileTypeError: Si el tipo no está soportado
        FileTooLargeError: Si el archivo es demasiado grande
    """
    if not file or not file.filename:
        raise InvalidFileError("No se proporcionó un archivo válido")

    # Sanitizar nombre
    safe_filename = sanitize_filename(file.filename)

    # Validar extensión
    validate_file_extension(safe_filename)

    # Validar tamaño
    validate_file_size(file, max_size)

    return safe_filename, True


def is_valid_docx_content(file_stream) -> bool:
    """
    Valida que el contenido del archivo sea realmente un DOCX válido
    verificando la firma de archivo ZIP (los DOCX son archivos ZIP).

    Args:
        file_stream: Stream del archivo

    Returns:
        True si es un DOCX válido, False en caso contrario
    """
    try:
        # Los archivos DOCX son ZIP, buscar la firma ZIP
        file_stream.seek(0)
        header = file_stream.read(4)
        file_stream.seek(0)

        # Firmas de archivo ZIP: PK\x03\x04 o PK\x05\x06 o PK\x07\x08
        zip_signatures = [
            b'PK\x03\x04',  # ZIP local file header
            b'PK\x05\x06',  # ZIP end of central directory
            b'PK\x07\x08',  # ZIP data descriptor
        ]

        return any(header.startswith(sig) for sig in zip_signatures)

    except Exception:
        return False
