#!/usr/bin/env python3
"""
CleanDoc - Punto de entrada
============================
Script principal para ejecutar la aplicación CleanDoc.

Uso:
    python run.py
    FLASK_ENV=production python run.py
"""

import os
import sys

from app import create_app

# Obtener entorno
env = os.getenv('FLASK_ENV', 'development')

# Crear aplicación
app = create_app(env)

if __name__ == "__main__":
    # Obtener configuración del servidor
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 4085)
    debug = app.config.get('DEBUG', False)

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
