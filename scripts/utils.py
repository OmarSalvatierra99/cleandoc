"""
CleanDoc - Utilidades y servicios auxiliares
============================================
Funciones de validacion, excepciones y limpieza de documentos.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any

from docx import Document
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


class CleanDocError(Exception):
    """Excepcion base para errores de CleanDoc."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidFileError(CleanDocError):
    """Excepcion cuando el archivo no es válido."""

    def __init__(self, message: str = "Archivo inválido"):
        super().__init__(message, status_code=400)


class FileProcessingError(CleanDocError):
    """Excepcion durante el procesamiento del archivo."""

    def __init__(self, message: str = "Error al procesar el archivo", filename: str = None):
        self.filename = filename
        full_message = f"{message}: {filename}" if filename else message
        super().__init__(full_message, status_code=500)


class NoFilesProvidedError(CleanDocError):
    """Excepcion cuando no se proporcionan archivos."""

    def __init__(self, message: str = "No se proporcionaron archivos"):
        super().__init__(message, status_code=400)


class FileTooLargeError(CleanDocError):
    """Excepcion cuando el archivo excede el tamaño máximo."""

    def __init__(self, message: str = "El archivo excede el tamaño máximo permitido"):
        super().__init__(message, status_code=413)


class UnsupportedFileTypeError(CleanDocError):
    """Excepcion cuando el tipo de archivo no esta soportado."""

    def __init__(self, message: str = "Tipo de archivo no soportado. Solo se permiten archivos .docx"):
        super().__init__(message, status_code=415)


def sanitize_filename(filename: str) -> str:
    """Sanitiza el nombre del archivo para prevenir path traversal."""
    if not filename:
        raise InvalidFileError("El nombre del archivo está vacío")

    safe_name = secure_filename(filename)

    if not safe_name:
        raise InvalidFileError(f"Nombre de archivo inválido: {filename}")

    if not re.match(r'^[\w\-. ]+$', safe_name):
        raise InvalidFileError(
            f"Nombre de archivo contiene caracteres no permitidos: {filename}"
        )

    return safe_name


def validate_file_extension(filename: str, allowed_extensions: set = {'.docx'}) -> bool:
    """Valida que el archivo tenga una extensión permitida."""
    if not filename:
        raise InvalidFileError("El nombre del archivo está vacío")

    file_ext = Path(filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise UnsupportedFileTypeError(
            f"Extensión '{file_ext}' no permitida. Solo se permiten: {', '.join(allowed_extensions)}"
        )

    return True


def validate_file_size(file: FileStorage, max_size: int = 50 * 1024 * 1024) -> bool:
    """Valida que el archivo no exceda el tamaño máximo."""
    if file is None:
        raise InvalidFileError("El archivo es None")

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
    """Valida completamente un archivo DOCX."""
    if not file or not file.filename:
        raise InvalidFileError("No se proporcionó un archivo válido")

    safe_filename = sanitize_filename(file.filename)
    validate_file_extension(safe_filename)
    validate_file_size(file, max_size)

    return safe_filename, True


def is_valid_docx_content(file_stream) -> bool:
    """Valida que el contenido sea un DOCX verificando firma ZIP."""
    try:
        file_stream.seek(0)
        header = file_stream.read(4)
        file_stream.seek(0)

        zip_signatures = [
            b'PK\x03\x04',
            b'PK\x05\x06',
            b'PK\x07\x08',
        ]

        return any(header.startswith(sig) for sig in zip_signatures)

    except Exception:
        return False


@dataclass
class CleaningStats:
    """Estadísticas de limpieza de un documento."""
    images_removed: int = 0
    institutional_paragraphs_cleaned: int = 0
    textboxes_cleaned: int = 0
    signature_section_removed: bool = False
    paragraphs_removed: int = 0
    errors: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'images_removed': self.images_removed,
            'institutional_paragraphs_cleaned': self.institutional_paragraphs_cleaned,
            'textboxes_cleaned': self.textboxes_cleaned,
            'signature_section_removed': self.signature_section_removed,
            'paragraphs_removed': self.paragraphs_removed,
            'has_errors': len(self.errors) > 0,
            'error_count': len(self.errors)
        }


class DocumentCleaner:
    """Limpiador de documentos DOCX institucionales."""

    PATTERN_ORGANO = re.compile(
        r"ÓRGANO\s+DE\s+FISCALIZACI[ÓO]N\s+SUPERIOR",
        re.IGNORECASE
    )

    PATTERN_DIRECCION = re.compile(
        r"DIRECCI[ÓO]N\s+DE\s+AUDITOR[IÍ]A\s+A\s+ENTES\s+ESTATALES",
        re.IGNORECASE
    )

    PATTERN_ELABORO = re.compile(
        r"Elabor[oó]",
        re.IGNORECASE
    )

    def __init__(self):
        self.stats = CleaningStats()

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text or "")

    def _remove_header_images(self, doc: Document) -> None:
        for section in doc.sections:
            try:
                drawings = section.header._element.xpath(".//*[local-name()='drawing']")
                for shape in drawings:
                    if shape.xpath("ancestor::*[local-name()='tbl']"):
                        continue

                    parent = shape.getparent()
                    if parent is not None:
                        parent.remove(shape)
                        self.stats.images_removed += 1

                picts = section.header._element.xpath(".//*[local-name()='pict']")
                for pict in picts:
                    if pict.xpath("ancestor::*[local-name()='tbl']"):
                        continue

                    if pict.xpath(".//*[local-name()='txbxContent']"):
                        continue

                    parent = pict.getparent()
                    if parent is not None:
                        parent.remove(pict)
                        self.stats.images_removed += 1

            except Exception as e:
                error_msg = f"Error eliminando imágenes de encabezado: {str(e)}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)

    def _clean_institutional_paragraphs(self, doc: Document) -> None:
        for p in list(doc.paragraphs):
            try:
                texto = p.text
                if self.PATTERN_ORGANO.search(texto) or self.PATTERN_DIRECCION.search(texto):
                    texto_limpio = self.PATTERN_ORGANO.sub("", texto)
                    texto_limpio = self.PATTERN_DIRECCION.sub("", texto_limpio).strip()

                    if texto_limpio:
                        if p.runs:
                            p.runs[0].text = texto_limpio
                            for run in p.runs[1:]:
                                run.text = ""
                            self.stats.institutional_paragraphs_cleaned += 1
                    else:
                        p._element.getparent().remove(p._element)
                        self.stats.paragraphs_removed += 1

            except Exception as e:
                error_msg = f"Error limpiando párrafo: {str(e)}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)

    def _clean_textboxes(self, xmlroot) -> None:
        try:
            for p in xmlroot.xpath(".//*[local-name()='txbxContent']//*[local-name()='p']"):
                ts = p.xpath(".//*[local-name()='t']")
                if not ts:
                    continue

                original = " ".join(
                    self._normalize_whitespace(t.text) for t in ts if t.text
                )

                nuevo = self.PATTERN_ORGANO.sub("", original)
                nuevo = self.PATTERN_DIRECCION.sub("", nuevo).strip()

                if nuevo != original:
                    ts[0].text = nuevo
                    for t in ts[1:]:
                        t.text = ""

                    self.stats.textboxes_cleaned += 1

                    if not nuevo:
                        parent = p.getparent()
                        if parent is not None:
                            parent.remove(p)

        except Exception as e:
            error_msg = f"Error limpiando textboxes: {str(e)}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)

    def _remove_signature_section(self, doc: Document) -> None:
        try:
            indice_inicio = None
            for i, p in enumerate(doc.paragraphs):
                if self.PATTERN_ELABORO.search(p.text.replace(" ", "")):
                    indice_inicio = i
                    break

            if indice_inicio is not None:
                paragraphs_to_remove = len(doc.paragraphs) - indice_inicio
                for j in range(len(doc.paragraphs) - 1, indice_inicio - 1, -1):
                    para = doc.paragraphs[j]
                    para._element.getparent().remove(para._element)

                self.stats.signature_section_removed = True
                self.stats.paragraphs_removed += paragraphs_to_remove

        except Exception as e:
            error_msg = f"Error eliminando sección de firmas: {str(e)}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)

    def clean_document(self, file_stream, filename: Optional[str] = None) -> tuple[BytesIO, CleaningStats]:
        self.stats = CleaningStats()

        try:
            doc = Document(file_stream)
            self._remove_header_images(doc)
            self._clean_institutional_paragraphs(doc)
            self._clean_textboxes(doc._element)
            for section in doc.sections:
                self._clean_textboxes(section.header._element)
                self._clean_textboxes(section.footer._element)
            self._remove_signature_section(doc)

            output = BytesIO()
            doc.save(output)
            output.seek(0)

            return output, self.stats

        except Exception as e:
            error_msg = f"Error procesando documento {filename or 'sin nombre'}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise FileProcessingError(error_msg, filename=filename)


_cleaner_instance: Optional[DocumentCleaner] = None


def get_cleaner() -> DocumentCleaner:
    """Obtiene la instancia singleton del limpiador."""
    global _cleaner_instance
    if _cleaner_instance is None:
        _cleaner_instance = DocumentCleaner()
    return _cleaner_instance
