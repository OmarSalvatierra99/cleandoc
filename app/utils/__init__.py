"""
CleanDoc - Utilidades
=====================
Paquete de utilidades para validación y manejo de errores.
"""

from .exceptions import (
    CleanDocError,
    InvalidFileError,
    FileProcessingError,
    NoFilesProvidedError,
    FileTooLargeError,
    UnsupportedFileTypeError
)

from .validators import (
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_docx_file,
    is_valid_docx_content
)

__all__ = [
    # Exceptions
    'CleanDocError',
    'InvalidFileError',
    'FileProcessingError',
    'NoFilesProvidedError',
    'FileTooLargeError',
    'UnsupportedFileTypeError',
    # Validators
    'sanitize_filename',
    'validate_file_extension',
    'validate_file_size',
    'validate_docx_file',
    'is_valid_docx_content',
]
