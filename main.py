#!/usr/bin/env python3
"""
Entrypoint principal para CF-Clearance-Scraper.

Soporta tanto modo CLI como modo API.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Agregar el directorio del paquete al path si es necesario
if __name__ == "__main__":
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from cf_clearance_scraper.cli.main import run_cli


async def main() -> None:
    """Función principal."""
    await run_cli()


if __name__ == "__main__":
    asyncio.run(main())
