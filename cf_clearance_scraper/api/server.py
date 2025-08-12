"""Servidor API para CF-Clearance-Scraper."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from ..core.solver import CloudflareSolver, ChallengePlatform
from ..core.turnstile import TurnstileSolver, TurnstileMode
from ..utils.user_agents import get_chrome_user_agent
from .models import (
    ScrapeRequest, ScrapeResponse, ErrorResponse, HealthResponse,
    TurnstileRequest, TurnstileResponse
)
from .auth import get_current_user, get_usage_stats

logger = logging.getLogger(__name__)


def format_uptime(seconds: float) -> str:
    """
    Formatea el uptime en unidades legibles.
    
    Parameters
    ----------
    seconds : float
        Tiempo en segundos.
        
    Returns
    -------
    str
        Tiempo formateado (ej: "2d 3h 45m 12s").
    """
    if seconds < 1:
        return f"{seconds:.2f}s"
    
    # Convertir a entero para cálculos
    total_seconds = int(seconds)
    
    # Definir unidades en segundos
    units = [
        ("w", 604800),  # semanas
        ("d", 86400),   # días
        ("h", 3600),    # horas
        ("m", 60),      # minutos
        ("s", 1),       # segundos
    ]
    
    parts = []
    
    for unit_name, unit_seconds in units:
        if total_seconds >= unit_seconds:
            unit_count = total_seconds // unit_seconds
            total_seconds %= unit_seconds
            parts.append(f"{unit_count}{unit_name}")
    
    if not parts:
        return "0s"
    
    # Limitar a las 3 unidades más significativas
    return " ".join(parts[:3])


class CFClearanceAPI:
    """Servidor API para CF-Clearance-Scraper."""
    
    def __init__(self, *, host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
        """
        Inicializa el servidor API.
        
        Parameters
        ----------
        host : str
            Host donde ejecutar el servidor.
        port : int
            Puerto donde ejecutar el servidor.
        debug : bool
            Habilitar modo debug.
        """
        self.host = host
        self.port = port
        self.debug = debug
        self.start_time = time.time()
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Crea la aplicación FastAPI."""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            """Maneja el ciclo de vida de la aplicación."""
            logger.info("Iniciando CF-Clearance API")
            yield
            logger.info("Deteniendo CF-Clearance API")

        app = FastAPI(
            title="CF-Clearance-Scraper API",
            description="API para obtener cookies de clearance de Cloudflare",
            version="1.0.0",
            lifespan=lifespan,
        )

        # Middleware CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Registrar rutas
        self._register_routes(app)
        
        # Manejador de excepciones global
        self._register_exception_handlers(app)

        return app

    def _register_routes(self, app: FastAPI) -> None:
        """Registra las rutas de la API."""

        @app.get("/health", response_model=HealthResponse)
        async def health_check() -> HealthResponse:
            """Health check del servicio."""
            uptime_seconds = time.time() - self.start_time
            return HealthResponse(
                status="healthy",
                version="1.0.0",
                uptime_seconds=uptime_seconds,
                uptime_formatted=format_uptime(uptime_seconds),
            )

        @app.post("/scrape", response_model=ScrapeResponse)
        async def scrape_clearance(
            request: ScrapeRequest, 
            current_user: Dict = Depends(get_current_user)
        ) -> ScrapeResponse:
            """
            Obtiene cookies de clearance de Cloudflare.
            
            Parameters
            ----------
            request : ScrapeRequest
                Parámetros de la solicitud.
                
            Returns
            -------
            ScrapeResponse
                Cookies obtenidas y metadatos.
                
            Raises
            ------
            HTTPException
                Si ocurre un error durante el scraping.
            """
            start_time = time.time()
            
            try:
                # Preparar user agent
                user_agent = request.user_agent or get_chrome_user_agent()
                
                # Ejecutar scraping
                result = await self._perform_scraping(
                    url=str(request.url),
                    user_agent=user_agent,
                    timeout=request.timeout,
                    proxy=request.proxy,
                    headless=request.headless,
                    http2=request.http2,
                    http3=request.http3,
                )
                
                processing_time = time.time() - start_time
                
                return ScrapeResponse(
                    success=True,
                    clearance_cookie=result["clearance_cookie"],
                    all_cookies=result["all_cookies"],
                    user_agent=result["user_agent"],
                    challenge_detected=result.get("challenge_type"),
                    processing_time=processing_time,
                )
                
            except Exception as e:
                logger.error(f"Error durante scraping: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=ErrorResponse(
                        error=str(e),
                        error_code="SCRAPING_ERROR",
                        details={"url": str(request.url)},
                    ).model_dump(),
                )

        @app.post("/turnstile", response_model=TurnstileResponse)
        async def solve_turnstile(
            request: TurnstileRequest,
            current_user: Dict = Depends(get_current_user)
        ) -> TurnstileResponse:
            """
            Resuelve desafíos de Turnstile de Cloudflare.
            
            Parameters
            ----------
            request : TurnstileRequest
                Parámetros de la solicitud Turnstile.
                
            Returns
            -------
            TurnstileResponse
                Resultado de la resolución de Turnstile.
                
            Raises
            ------
            HTTPException
                Si ocurre un error durante la resolución.
            """
            try:
                # Validar modo
                if request.mode not in ["auto_detect", "manual"]:
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponse(
                            error="Modo inválido. Use 'auto_detect' o 'manual'",
                            error_code="INVALID_MODE",
                        ).model_dump(),
                    )
                
                # Validar sitekey en modo manual
                if request.mode == "manual" and not request.sitekey:
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponse(
                            error="Se requiere sitekey en modo manual",
                            error_code="MISSING_SITEKEY",
                        ).model_dump(),
                    )
                
                # Preparar user agent
                user_agent = request.user_agent or get_chrome_user_agent()
                
                # Resolver Turnstile
                async with TurnstileSolver(
                    user_agent=user_agent,
                    timeout=request.timeout,
                    headless=request.headless,
                    proxy=request.proxy,
                ) as solver:
                    
                    mode = TurnstileMode.AUTO_DETECT if request.mode == "auto_detect" else TurnstileMode.MANUAL
                    
                    result = await solver.solve_turnstile(
                        url=str(request.url),
                        sitekey=request.sitekey,
                        mode=mode,
                        action=request.action,
                        cdata=request.cdata,
                    )
                
                return TurnstileResponse(
                    success=result.success,
                    token=result.token,
                    sitekey=result.sitekey,
                    processing_time=result.processing_time,
                    error_message=result.error_message,
                    challenge_detected=result.challenge_detected,
                    mode_used=request.mode,
                )
                
            except Exception as e:
                logger.error(f"Error resolviendo Turnstile: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=ErrorResponse(
                        error=str(e),
                        error_code="TURNSTILE_ERROR",
                        details={"url": str(request.url)},
                    ).model_dump(),
                )

        @app.post("/turnstile/detect", response_model=Dict[str, Any])
        async def detect_turnstile_sitekey(
            request: Dict[str, str],
            current_user: Dict = Depends(get_current_user)
        ) -> Dict[str, Any]:
            """
            Detecta automáticamente el sitekey de Turnstile en una página.
            
            Parameters
            ----------
            request : Dict[str, str]
                Debe contener 'url' y opcionalmente 'user_agent'.
                
            Returns
            -------
            Dict[str, Any]
                Información del sitekey detectado.
            """
            try:
                url = request.get("url")
                if not url:
                    raise HTTPException(
                        status_code=400,
                        detail={"error": "Se requiere el parámetro 'url'"}
                    )
                
                user_agent = request.get("user_agent") or get_chrome_user_agent()
                
                async with TurnstileSolver(user_agent=user_agent) as solver:
                    sitekey = await solver.detect_sitekey(url)
                
                return {
                    "success": bool(sitekey),
                    "sitekey": sitekey,
                    "url": url,
                    "detected": bool(sitekey),
                }
                
            except Exception as e:
                logger.error(f"Error detectando sitekey: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={"error": str(e)}
                )

        @app.get("/")
        async def root() -> Dict[str, Any]:
            """Endpoint raíz con información básica."""
            return {
                "name": "CF-Clearance-Scraper API",
                "version": "1.0.0",
                "docs": "/docs",
                "health": "/health",
                "endpoints": {
                    "cf_clearance": "/scrape",
                    "turnstile": "/turnstile", 
                    "turnstile_detect": "/turnstile/detect"
                }
            }

        @app.get("/admin/stats")
        async def get_api_stats(current_user: Dict = Depends(get_current_user)) -> Dict:
            """
            Obtiene estadísticas de uso de la API (solo administradores).
            """
            # Solo permitir acceso a administradores
            if current_user.get("name") != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="Acceso denegado. Solo administradores."
                )
            
            stats = get_usage_stats()
            return {
                "success": True,
                "stats": stats,
                "timestamp": time.time()
            }

    def _register_exception_handlers(self, app: FastAPI) -> None:
        """Registra manejadores de excepciones."""

        @app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
            """Maneja excepciones globales."""
            logger.error(f"Error no manejado: {exc}")
            
            error_response = ErrorResponse(
                error="Error interno del servidor",
                error_code="INTERNAL_ERROR",
                details={"path": request.url.path},
            )
            
            return JSONResponse(
                status_code=500,
                content=error_response.model_dump(),
            )

    async def _perform_scraping(
        self,
        *,
        url: str,
        user_agent: str,
        timeout: float,
        proxy: str | None = None,
        headless: bool = False,
        http2: bool = True,
        http3: bool = True,
    ) -> Dict[str, Any]:
        """
        Ejecuta el proceso de scraping.
        
        Parameters
        ----------
        url : str
            URL objetivo.
        user_agent : str
            User agent a usar.
        timeout : float
            Timeout en segundos.
        proxy : str | None
            Proxy a usar.
        headless : bool
            Modo headless.
        http2 : bool
            Habilitar HTTP/2.
        http3 : bool
            Habilitar HTTP/3.
            
        Returns
        -------
        Dict[str, Any]
            Resultado del scraping.
            
        Raises
        ------
        RuntimeError
            Si no se puede obtener la cookie de clearance.
        """
        async with CloudflareSolver(
            user_agent=user_agent,
            timeout=timeout,
            proxy=proxy,
            headless=headless,
            http2=http2,
            http3=http3,
        ) as solver:
            
            # Navegar a la URL
            await solver.navigate_to(url)
            
            # Obtener cookies iniciales
            all_cookies = await solver.get_cookies()
            clearance_cookie = solver.extract_clearance_cookie(all_cookies)
            challenge_type = None
            
            # Si no hay clearance cookie, intentar resolver desafío
            if clearance_cookie is None:
                await solver.set_user_agent_metadata(await solver.get_user_agent())
                challenge_platform = await solver.detect_challenge()
                
                if challenge_platform is None:
                    raise RuntimeError("No se detectó desafío de Cloudflare y no hay cookie de clearance")
                
                challenge_type = challenge_platform.value
                success = await solver.solve_challenge()
                
                if not success:
                    raise RuntimeError("No se pudo resolver el desafío de Cloudflare")
                
                # Obtener cookies después de resolver
                all_cookies = await solver.get_cookies()
                clearance_cookie = solver.extract_clearance_cookie(all_cookies)
                
                if clearance_cookie is None:
                    raise RuntimeError("No se obtuvo cookie de clearance después de resolver el desafío")
            
            user_agent_final = await solver.get_user_agent()
            
            return {
                "clearance_cookie": clearance_cookie,
                "all_cookies": all_cookies,
                "user_agent": user_agent_final,
                "challenge_type": challenge_type,
            }

    def run(self) -> None:
        """Ejecuta el servidor."""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info",
        )

    async def run_async(self) -> None:
        """Ejecuta el servidor de forma asíncrona."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info",
        )
        server = uvicorn.Server(config)
        await server.serve() 