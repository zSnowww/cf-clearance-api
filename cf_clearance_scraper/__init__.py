"""
CF-Clearance-Scraper: Un scraper para obtener cookies de clearance de Cloudflare.

Este paquete proporciona herramientas para resolver desafíos de Cloudflare automáticamente
y obtener las cookies necesarias para hacer bypass a la protección.
"""

from __future__ import annotations

from .core import (
    # Clases base
    BaseSolver,
    ChallengeType,
    SolverMode,
    BaseResult,
    ClearanceResult,
    TurnstileResult,
    UnifiedCloudflareDetector,
    
    # Solvers específicos
    CloudflareSolver,
    TurnstileSolver,
    
    # Compatibilidad hacia atrás
    ChallengePlatform,
    TurnstileMode,
)
from .api.server import CFClearanceAPI
from .utils.user_agents import get_chrome_user_agent
from .utils.cookies import format_cookie_header
from .utils.commands import render_http_command

__version__ = "2.0.0"
__author__ = "CF-Clearance-Scraper Team"

__all__ = [
    # Clases base
    "BaseSolver",
    "ChallengeType", 
    "SolverMode",
    "BaseResult",
    "ClearanceResult",
    "TurnstileResult",
    "UnifiedCloudflareDetector",
    
    # Solvers específicos
    "CloudflareSolver",
    "TurnstileSolver",
    
    # API
    "CFClearanceAPI",
    
    # Utilidades
    "get_chrome_user_agent",
    "format_cookie_header",
    "render_http_command",
    
    # Compatibilidad hacia atrás
    "ChallengePlatform",
    "TurnstileMode",
] 