"""
CleanDoc - Excepciones personalizadas
======================================
Define excepciones específicas para manejo de errores.
"""


class CleanDocError(Exception):
    """Excepción base para errores de CleanDoc"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidFileError(CleanDocError):
    """Excepción cuando el archivo no es válido"""
    def __init__(self, message: str = "Archivo inválido"):
        super().__init__(message, status_code=400)


class FileProcessingError(CleanDocError):
    """Excepción durante el procesamiento del archivo"""
    def __init__(self, message: str = "Error al procesar el archivo", filename: str = None):
        self.filename = filename
        full_message = f"{message}: {filename}" if filename else message
        super().__init__(full_message, status_code=500)


class NoFilesProvidedError(CleanDocError):
    """Excepción cuando no se proporcionan archivos"""
    def __init__(self, message: str = "No se proporcionaron archivos"):
        super().__init__(message, status_code=400)


class FileTooLargeError(CleanDocError):
    """Excepción cuando el archivo excede el tamaño máximo"""
    def __init__(self, message: str = "El archivo excede el tamaño máximo permitido"):
        super().__init__(message, status_code=413)


class UnsupportedFileTypeError(CleanDocError):
    """Excepción cuando el tipo de archivo no está soportado"""
    def __init__(self, message: str = "Tipo de archivo no soportado. Solo se permiten archivos .docx"):
        super().__init__(message, status_code=415)
