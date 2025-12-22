# CleanDoc v2.0 - Sistema de Limpieza de Documentos Institucionales

🔗 **Live:** https://cleandoc.omar-xyz.shop/

CleanDoc es una herramienta profesional de alta confiabilidad diseñada para el **Órgano de Fiscalización Superior del Estado de Tlaxcala (OFS)** para limpiar documentos DOCX oficiales eliminando encabezados institucionales, imágenes y secciones de firmas. Estandariza documentos para procesamiento posterior preservando únicamente el contenido esencial de auditoría.

---

## 🎯 Características Principales

### Limpieza Automatizada
- ✅ Eliminación de encabezados institucionales (Órgano de Fiscalización Superior, Dirección de Auditoría...)
- ✅ Eliminación de imágenes en headers (preservando las contenidas en tablas)
- ✅ Limpieza de texto institucional repetitivo dentro de textboxes (documento, header, footer)
- ✅ Eliminación de todo contenido desde el primer "Elaboró" hasta el final
- ✅ Procesamiento por lotes de múltiples archivos DOCX (salida ZIP)

### Interfaz Moderna (v2.0)
- 🎨 **Drag & Drop**: Arrastra archivos directamente a la interfaz
- 📊 **Vista previa**: Visualiza archivos seleccionados antes de procesar
- ⚡ **Indicador de progreso**: Seguimiento visual en tiempo real
- 📈 **Estadísticas**: Reporte detallado de elementos limpiados
- 📱 **Responsive**: Diseño adaptable a móviles y tablets

### Arquitectura Profesional
- 🏗️ **Arquitectura modular**: Separación clara de responsabilidades
- 🔒 **Seguridad robusta**: Headers HTTP de seguridad, validación de archivos, sanitización
- 📝 **Logging completo**: Sistema de logs con rotación
- 🧪 **Tests unitarios**: Cobertura de la lógica principal
- 📖 **Documentación**: Type hints, docstrings, comentarios explicativos

---

## 📁 Estructura del Proyecto

```
CleanDoc/
├── app/
│   ├── __init__.py              # Factory de la aplicación Flask
│   ├── config.py                # Configuración centralizada
│   ├── routes/
│   │   ├── __init__.py
│   │   └── main.py              # Rutas y endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   └── document_cleaner.py  # Lógica de limpieza de documentos
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── validators.py        # Validación y sanitización
│   │   └── exceptions.py        # Excepciones personalizadas
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css        # Estilos modernos
│   │   └── img/
│   │       └── ofs_logo.png
│   └── templates/
│       └── index.html           # Interfaz web
├── tests/
│   ├── __init__.py
│   └── test_document_cleaner.py # Tests unitarios
├── logs/                        # Logs de la aplicación (auto-creado)
├── .env.example                 # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt
├── run.py                       # Punto de entrada
└── README.md
```

---

## 🚀 Instalación

### Requisitos Previos
- Python 3.8 o superior
- pip

### Pasos de Instalación

```bash
# Clonar el repositorio
git clone https://github.com/OmarSalvatierra99/CleanDoc.git
cd CleanDoc

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (opcional)
cp .env.example .env
# Editar .env según necesidades

# Ejecutar la aplicación
python run.py
```

La aplicación estará disponible en `http://localhost:4085`

---

## 🔧 Configuración

### Variables de Entorno

Crea un archivo `.env` basado en `.env.example`:

```env
# Entorno de la aplicación
FLASK_ENV=development          # development, production, testing

# Seguridad
SECRET_KEY=tu-clave-secreta   # CAMBIAR EN PRODUCCIÓN

# Servidor
HOST=0.0.0.0
PORT=4085
DEBUG=False

# Logging
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/cleandoc.log

# Uploads (opcional)
UPLOAD_FOLDER=/tmp/cleandoc_uploads
```

### Configuración para Producción

```bash
# Usar gunicorn para producción
gunicorn -w 4 -b 0.0.0.0:4085 "app:create_app('production')"
```

---

## 📖 Uso

### Interfaz Web

1. **Accede** a la aplicación web
2. **Arrastra archivos** `.docx` o haz clic para seleccionar
3. **Revisa** la vista previa de archivos seleccionados
4. **Procesa** haciendo clic en "Procesar y limpiar"
5. **Descarga** automática del archivo limpio o ZIP

### Ejemplo de Procesamiento

```
Input:  documento.docx
        ├── Headers con logos institucionales
        ├── "ÓRGANO DE FISCALIZACIÓN SUPERIOR"
        ├── Contenido de auditoría (PRESERVADO)
        ├── "Elaboró: Juan Pérez"
        └── Firmas y Vo.Bo.

Output: limpia_documento.docx
        └── Contenido de auditoría (LIMPIO)

Elementos eliminados:
  • 3 imágenes de encabezados
  • 5 párrafos institucionales
  • 2 textboxes limpios
  • Sección de firmas completa
```

---

## 🧪 Tests

Ejecutar los tests unitarios:

```bash
# Ejecutar todos los tests
python -m unittest discover tests

# Ejecutar un test específico
python -m unittest tests.test_document_cleaner

# Con más detalle
python -m unittest tests.test_document_cleaner -v
```

---

## 🔒 Seguridad

### Características de Seguridad Implementadas

- ✅ **Validación de archivos**: Verificación de extensión y contenido
- ✅ **Sanitización de nombres**: Prevención de path traversal
- ✅ **Límite de tamaño**: 50 MB máximo por archivo
- ✅ **Headers HTTP**: CSP, X-Frame-Options, HSTS, etc.
- ✅ **Procesamiento en memoria**: Sin archivos temporales en disco
- ✅ **Manejo de errores**: Sin exposición de información sensible

### Headers de Seguridad

```
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; ...
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

---

## 🎨 Tecnologías Utilizadas

### Backend
- **Flask 3.0.3** - Framework web minimalista
- **python-docx 1.1.2** - Manipulación de archivos DOCX
- **lxml 5.3.0** - Parser XML de alto rendimiento
- **gunicorn 23.0.0** - Servidor WSGI para producción
- **python-dotenv 1.0.1** - Gestión de variables de entorno

### Frontend
- **HTML5** - Estructura semántica
- **CSS3** - Diseño moderno con variables CSS, flexbox, grid
- **JavaScript Vanilla** - Sin frameworks, Fetch API
- **Google Fonts (Inter)** - Tipografía moderna

---

## 📊 API

### Endpoints

#### `GET /`
Página principal de la aplicación.

#### `GET /health`
Health check para monitoreo.

**Response:**
```json
{
  "status": "healthy",
  "service": "CleanDoc",
  "version": "2.0.0"
}
```

#### `POST /limpiar_cedula`
Procesa y limpia uno o más archivos DOCX.

**Request:**
- `Content-Type: multipart/form-data`
- `archivo`: Archivo(s) DOCX

**Response:**
- **1 archivo**: DOCX limpio (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
- **Múltiples archivos**: ZIP con archivos limpios + estadísticas (`application/zip`)

**Headers de respuesta:**
```
X-CleanDoc-Images-Removed: 3
X-CleanDoc-Paragraphs-Cleaned: 5
X-CleanDoc-Signature-Removed: True
X-CleanDoc-Total-Files: 2
```

---

## 🐛 Solución de Problemas

### Error: "ModuleNotFoundError"
```bash
# Asegúrate de activar el entorno virtual
source venv/bin/activate
pip install -r requirements.txt
```

### Error: "Port already in use"
```bash
# Cambiar puerto en .env
PORT=5000
```

### Los logs no se crean
```bash
# Verificar permisos del directorio
mkdir -p logs
chmod 755 logs
```

---

## 📝 Registro de Cambios

### v2.0.0 (2025-01-XX)
- ✨ Arquitectura modular completa
- ✨ Interfaz drag & drop moderna
- ✨ Sistema de estadísticas en tiempo real
- ✨ Logging profesional con rotación
- ✨ Validación y sanitización robusta
- ✨ Headers de seguridad HTTP
- ✨ Tests unitarios
- ✨ Type hints y documentación completa

### v1.0.0
- ✅ Funcionalidad básica de limpieza
- ✅ Interfaz web simple
- ✅ Procesamiento por lotes

---

## 👥 Autor

**Omar Gabriel Salvatierra Garcia**
Desarrollador de Software Institucional
Órgano de Fiscalización Superior del Estado de Tlaxcala

---

## 📄 Licencia

© 2025 Órgano de Fiscalización Superior del Estado de Tlaxcala
Software de uso interno institucional.

---

## 🤝 Contribuir

Este es un proyecto de uso interno del OFS. Para sugerencias o reportes de bugs, contacta al equipo de desarrollo interno.

---

## 📞 Soporte

Para soporte técnico, contacta al departamento de TI del OFS Tlaxcala.

---

**CleanDoc v2.0** - Limpieza profesional de documentos institucionales 🚀
