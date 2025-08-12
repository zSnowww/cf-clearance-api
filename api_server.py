#!/usr/bin/env python3
"""
Script para ejecutar el servidor API de CF-Clearance-Scraper.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Agregar el directorio del paquete al path si es necesario
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from cf_clearance_scraper.api.server import CFClearanceAPI


def parse_args() -> argparse.Namespace:
    """Parsea argumentos de línea de comandos para el servidor API."""
    parser = argparse.ArgumentParser(
        description="Servidor API para CF-Clearance-Scraper"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host donde ejecutar el servidor (default: 0.0.0.0)",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Puerto donde ejecutar el servidor (default: 8000)",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Habilitar modo debug",
    )
    
    return parser.parse_args()


def main() -> None:
    """Función principal del servidor API."""
    args = parse_args()
    
    # Configurar logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        level=level,
    )
    
    # Crear y ejecutar servidor
    api = CFClearanceAPI(
        host=args.host,
        port=args.port,
        debug=args.debug,
    )
    
    print(f"🚀 Iniciando CF-Clearance API en http://{args.host}:{args.port}")
    print(f"📖 Documentación disponible en http://{args.host}:{args.port}/docs")
    
    try:
        api.run()
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido")


if __name__ == "__main__":
    main() 