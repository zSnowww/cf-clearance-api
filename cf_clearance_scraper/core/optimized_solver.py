"""
Solver optimizado que mantiene una instancia de navegador persistente.

Basado en la documentación de zendriver para máxima eficiencia.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import asynccontextmanager
from enum import Enum

import zendriver
from selenium_authenticated_proxy import SeleniumAuthenticatedProxy

from .solver import CloudflareSolver
from .turnstile import TurnstileSolver
from ..utils.user_agents import get_chrome_user_agent

logger = logging.getLogger(__name__)


def format_cookies_for_log(cookies: List[Dict[str, Any]], user_agent: str = None) -> str:
    """
    Formatea las cookies para logging de manera legible.
    
    Args:
        cookies: Lista de cookies obtenidas
        user_agent: User agent utilizado
        
    Returns:
        String formateado con información de cookies
    """
    if not cookies:
        return "❌ No se obtuvieron cookies"
    
    important_cookies = []
    other_cookies = []
    
    for cookie in cookies:
        name = cookie.get('name', '')
        value = cookie.get('value', '')
        domain = cookie.get('domain', '')
        
        if name in ['cf_clearance', '__cf_bm', 'cf_bm', '_cfuvid']:
            important_cookies.append(f"🔑 {name}: {value[:20]}...{value[-10:] if len(value) > 30 else value}")
        else:
            other_cookies.append(f"   {name}: {value[:15]}...")
    
    result = []
    if important_cookies:
        result.append("🍪 COOKIES IMPORTANTES:")
        result.extend(important_cookies)
    
    if other_cookies:
        result.append(f"📝 Otras cookies ({len(other_cookies)}):")
        result.extend(other_cookies[:3])  # Solo las primeras 3
        if len(other_cookies) > 3:
            result.append(f"   ... y {len(other_cookies) - 3} más")
    
    if user_agent:
        result.append(f"🌐 User-Agent: {user_agent[:50]}...")
    
    return "\n".join(result)


async def clear_browser_data(browser: zendriver.Browser) -> bool:
    """
    Limpia datos del navegador para evitar interferencias entre requests.
    
    Args:
        browser: Instancia del navegador Zendriver
        
    Returns:
        True si la limpieza fue exitosa, False en caso contrario
    """
    try:
        # Limpiar cookies
        await browser.cookies.clear()
        
        # Limpiar localStorage y sessionStorage usando la API de Zendriver
        await browser.evaluate("""
            try {
                localStorage.clear();
                sessionStorage.clear();
                // Limpiar cache si está disponible
                if ('caches' in window) {
                    caches.keys().then(names => {
                        names.forEach(name => {
                            caches.delete(name);
                        });
                    });
                }
                return true;
            } catch (e) {
                console.log('Error limpiando datos:', e);
                return false;
            }
        """)
        
        # Navegar a about:blank para limpiar la página actual
        await browser.get("about:blank")
        
        logger.debug("🧹 Datos del navegador limpiados exitosamente")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Error limpiando datos del navegador: {e}")
        return False


class RequestPriority(Enum):
    """Prioridades de requests."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SolverRequest:
    """Request para el solver optimizado."""
    
    id: str
    solver_type: str  # 'clearance' o 'turnstile'
    url: str
    priority: RequestPriority
    timeout: float
    params: Dict[str, Any]
    
    # Resultados
    result_event: asyncio.Event
    result_data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None
    
    def __lt__(self, other):
        """Comparación para PriorityQueue."""
        if not isinstance(other, SolverRequest):
            return NotImplemented
        # Menor valor = mayor prioridad
        return self.priority.value < other.priority.value


class OptimizedCloudflareManager:
    """
    Manager optimizado que mantiene navegadores persistentes.
    
    Usa una instancia de navegador por tipo de solver para máxima eficiencia,
    basándose en la arquitectura actual de zendriver.
    """
    
    def __init__(
        self,
        max_concurrent_requests: int = 10,
        default_timeout: float = 30.0,
        user_agent: Optional[str] = None,
        headless: bool = True,
        proxy: Optional[str] = None,
    ):
        self.max_concurrent_requests = max_concurrent_requests
        self.default_timeout = default_timeout
        self.headless = headless
        self.proxy = proxy
        self.user_agent = user_agent or get_chrome_user_agent()
        
        # Solvers persistentes
        self._clearance_solver: Optional[CloudflareSolver] = None
        self._turnstile_solver: Optional[TurnstileSolver] = None
        
        # Queue system
        self.request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.processing_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.is_running = False
        
        # Workers
        self.worker_tasks: list[asyncio.Task] = []
        
        # Stats
        self.stats = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "clearance_requests": 0,
            "turnstile_requests": 0,
            "avg_processing_time": 0.0,
            "queue_size": 0,
        }
        
        logger.info(f"OptimizedCloudflareManager inicializado: max_concurrent={max_concurrent_requests}")

    async def start(self) -> None:
        """Inicia el manager y los solvers persistentes."""
        if self.is_running:
            logger.warning("Manager ya está ejecutándose")
            return
        
        logger.info("Iniciando OptimizedCloudflareManager...")
        
        try:
            # Inicializar solvers
            await self._init_solvers()
            
            # Iniciar workers
            self._start_workers()
            
            self.is_running = True
            logger.info("OptimizedCloudflareManager iniciado exitosamente")
            
        except Exception as e:
            logger.error(f"Error iniciando manager: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Detiene el manager y limpia recursos."""
        if not self.is_running:
            return
        
        logger.info("Deteniendo OptimizedCloudflareManager...")
        self.is_running = False
        
        # Cancelar workers
        for task in self.worker_tasks:
            task.cancel()
        
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # Cerrar solvers
        if self._clearance_solver:
            await self._clearance_solver.stop()
            self._clearance_solver = None
        
        if self._turnstile_solver:
            await self._turnstile_solver.stop()
            self._turnstile_solver = None
        
        logger.info("OptimizedCloudflareManager detenido")

    async def _init_solvers(self) -> None:
        """Inicializa los solvers persistentes."""
        # CloudflareSolver
        self._clearance_solver = CloudflareSolver(
            user_agent=self.user_agent,
            timeout=self.default_timeout,
            headless=self.headless,
            proxy=self.proxy,
        )
        await self._clearance_solver.start()
        logger.info("CloudflareSolver persistente iniciado")
        
        # TurnstileSolver
        self._turnstile_solver = TurnstileSolver(
            user_agent=self.user_agent,
            timeout=self.default_timeout,
            headless=self.headless,
            proxy=self.proxy,
        )
        await self._turnstile_solver.start()
        logger.info("TurnstileSolver persistente iniciado")

    def _start_workers(self) -> None:
        """Inicia workers para procesar requests."""
        # Usar menos workers que el semáforo para evitar bloqueos
        num_workers = min(5, self.max_concurrent_requests)
        
        for i in range(num_workers):
            task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.worker_tasks.append(task)
        
        logger.info(f"Iniciados {num_workers} workers")

    async def _worker_loop(self, worker_id: str) -> None:
        """Loop principal del worker."""
        logger.debug(f"Worker {worker_id} iniciado")
        
        while self.is_running:
            try:
                # Obtener request de la cola
                try:
                    request = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Procesar con semáforo para limitar concurrencia
                async with self.processing_semaphore:
                    await self._process_request(worker_id, request)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en worker {worker_id}: {e}")
                await asyncio.sleep(1)
        
        logger.debug(f"Worker {worker_id} detenido")

    async def _process_request(self, worker_id: str, request: SolverRequest) -> None:
        """Procesa un request individual."""
        start_time = time.time()
        
        try:
            logger.debug(f"Worker {worker_id} procesando {request.solver_type} request {request.id}")
            
            # Seleccionar solver y navegador
            if request.solver_type == "clearance":
                result = await self._process_clearance_request(request)
                browser = self._clearance_solver.driver if hasattr(self._clearance_solver, 'driver') else None
                self.stats["clearance_requests"] += 1
            elif request.solver_type == "turnstile":
                result = await self._process_turnstile_request(request)
                browser = self._turnstile_solver.driver if hasattr(self._turnstile_solver, 'driver') else None
                self.stats["turnstile_requests"] += 1
            else:
                raise ValueError(f"Tipo de solver desconocido: {request.solver_type}")
            
            # Registrar cookies si el request fue exitoso
            if result.get("success"):
                cookies = result.get("all_cookies", [])
                user_agent = result.get("user_agent")
                
                if cookies:
                    cookie_log = format_cookies_for_log(cookies, user_agent)
                    logger.info(f"🍪 Cookies obtenidas para {request.url}:\n{cookie_log}")
                    
                    # Guardar cookies en formato JSON para debugging
                    result["cookies_raw"] = cookies
                    result["cookie_count"] = len(cookies)
                    
                    # Extraer cookies importantes para fácil acceso
                    important_cookies = {}
                    for cookie in cookies:
                        name = cookie.get('name', '')
                        if name in ['cf_clearance', '__cf_bm', 'cf_bm', '_cfuvid']:
                            important_cookies[name] = cookie.get('value', '')
                    result["important_cookies"] = important_cookies
                else:
                    logger.warning(f"⚠️ No se obtuvieron cookies para {request.url}")
            
            # Limpiar datos del navegador después del request
            if browser:
                cleanup_success = await clear_browser_data(browser)
                if cleanup_success:
                    logger.debug(f"🧹 Datos limpiados exitosamente para worker {worker_id}")
                else:
                    logger.warning(f"⚠️ Limpieza parcial para worker {worker_id}")
            
            # Guardar resultado
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            result["worker_id"] = worker_id
            
            request.result_data = result
            request.result_event.set()
            
            self.stats["completed_requests"] += 1
            self._update_avg_processing_time(processing_time)
            
            logger.info(f"✅ Request {request.id} completado en {processing_time:.2f}s por worker {worker_id}")
            
        except Exception as e:
            logger.error(f"💥 Error procesando request {request.id}: {e}")
            request.error = e
            request.result_event.set()
            self.stats["failed_requests"] += 1
        
        finally:
            self.stats["queue_size"] = self.request_queue.qsize()

    async def _process_clearance_request(self, request: SolverRequest) -> Dict[str, Any]:
        """Procesa un request de clearance."""
        solver = self._clearance_solver
        
        # Usar el método solve unificado
        result = await solver.solve(request.url, **request.params)
        
        if result.success:
            return {
                "success": True,
                "url": request.url,
                "challenge_type": result.challenge_type.value if result.challenge_type else None,
                "clearance_cookie": result.clearance_cookie,
                "all_cookies": result.all_cookies,
                "user_agent": result.user_agent,
                "challenge_detected": result.challenge_detected,
            }
        else:
            return {
                "success": False,
                "url": request.url,
                "error_message": result.error_message,
                "challenge_type": result.challenge_type.value if result.challenge_type else None,
            }

    async def _process_turnstile_request(self, request: SolverRequest) -> Dict[str, Any]:
        """Procesa un request de Turnstile."""
        solver = self._turnstile_solver
        
        # Usar el método solve unificado
        result = await solver.solve(request.url, **request.params)
        
        if result.success:
            return {
                "success": True,
                "url": request.url,
                "challenge_type": "turnstile",
                "token": result.token,
                "sitekey": result.sitekey,
                "user_agent": result.user_agent,
                "challenge_detected": result.challenge_detected,
            }
        else:
            return {
                "success": False,
                "url": request.url,
                "error_message": result.error_message,
                "sitekey": result.sitekey,
            }

    def _update_avg_processing_time(self, processing_time: float) -> None:
        """Actualiza el tiempo promedio de procesamiento."""
        if self.stats["completed_requests"] > 0:
            current_avg = self.stats["avg_processing_time"]
            total_requests = self.stats["completed_requests"]
            
            self.stats["avg_processing_time"] = (
                (current_avg * (total_requests - 1) + processing_time) / total_requests
            )

    @asynccontextmanager
    async def solve_clearance(
        self,
        url: str,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: Optional[float] = None,
        **params: Any,
    ):
        """
        Context manager para resolver desafíos de clearance.
        
        Usage:
        async with manager.solve_clearance("https://site.com") as result:
            if result["success"]:
                print(result["clearance_cookie"])
        """
        yield await self._submit_request(
            solver_type="clearance",
            url=url,
            priority=priority,
            timeout=timeout or self.default_timeout,
            params=params,
        )

    @asynccontextmanager
    async def solve_turnstile(
        self,
        url: str,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: Optional[float] = None,
        **params: Any,
    ):
        """
        Context manager para resolver desafíos de Turnstile.
        
        Usage:
        async with manager.solve_turnstile("https://site.com") as result:
            if result["success"]:
                print(result["token"])
        """
        yield await self._submit_request(
            solver_type="turnstile",
            url=url,
            priority=priority,
            timeout=timeout or self.default_timeout,
            params=params,
        )

    async def _submit_request(
        self,
        solver_type: str,
        url: str,
        priority: RequestPriority,
        timeout: float,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Envía un request al queue y espera el resultado."""
        if not self.is_running:
            raise RuntimeError("Manager no está ejecutándose")
        
        # Crear request
        request = SolverRequest(
            id=str(uuid.uuid4()),
            solver_type=solver_type,
            url=url,
            priority=priority,
            timeout=timeout,
            params=params,
            result_event=asyncio.Event(),
        )
        
        # Agregar a la cola
        self.stats["total_requests"] += 1
        await self.request_queue.put(request)
        
        logger.debug(f"Request {request.id} ({solver_type}) agregado a la cola")
        
        try:
            # Esperar resultado
            await asyncio.wait_for(request.result_event.wait(), timeout=timeout + 10)
            
            if request.error:
                raise request.error
            
            return request.result_data or {"success": False, "error": "No result data"}
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout esperando resultado de {request.id}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del manager."""
        return {
            **self.stats,
            "is_running": self.is_running,
            "active_solvers": {
                "clearance": self._clearance_solver is not None,
                "turnstile": self._turnstile_solver is not None,
            },
        }


# Instancia global
_optimized_manager: Optional[OptimizedCloudflareManager] = None


async def get_optimized_manager(**kwargs) -> OptimizedCloudflareManager:
    """Obtiene la instancia global del manager optimizado."""
    global _optimized_manager
    if _optimized_manager is None or not _optimized_manager.is_running:
        _optimized_manager = OptimizedCloudflareManager(**kwargs)
        await _optimized_manager.start()
    return _optimized_manager


async def cleanup_optimized_manager() -> None:
    """Limpia la instancia global."""
    global _optimized_manager
    if _optimized_manager:
        await _optimized_manager.stop()
        _optimized_manager = None
