"""Módulo core con la funcionalidad principal del solver."""

from __future__ import annotations

from .base import (
    BaseSolver,
    ChallengeType,
    SolverMode,
    BaseResult,
    ClearanceResult,
    TurnstileResult,
    UnifiedCloudflareDetector,
)
from .solver import CloudflareSolver, ChallengePlatform
from .turnstile import TurnstileSolver, TurnstileMode
# Browser manager removido - usar optimized_solver
from .optimized_solver import (
    OptimizedCloudflareManager,
    RequestPriority,
    get_optimized_manager,
    cleanup_optimized_manager,
)

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
    
    # Compatibilidad hacia atrás
    "ChallengePlatform",
    "TurnstileMode",
    
    # Sistema optimizado recomendado
    "OptimizedCloudflareManager",
    "RequestPriority",
    "get_optimized_manager", 
    "cleanup_optimized_manager",
] 