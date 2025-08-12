"""
Clase base para todos los solvers de Cloudflare.

Define la interfaz común y funcionalidades compartidas entre
CloudflareSolver y TurnstileSolver.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Dict, Protocol

import zendriver
from selenium_authenticated_proxy import SeleniumAuthenticatedProxy

from ..utils.user_agents import get_chrome_user_agent

logger = logging.getLogger(__name__)


class ChallengeType(Enum):
    """Tipos de desafíos de Cloudflare."""
    
    # Desafíos de CF-Clearance
    JAVASCRIPT = "javascript"
    MANAGED = "managed" 
    INTERACTIVE = "interactive"
    
    # Turnstile
    TURNSTILE = "turnstile"


class SolverMode(Enum):
    """Modos de operación del solver."""
    
    AUTO_DETECT = "auto_detect"
    MANUAL = "manual"


@dataclass
class BaseResult:
    """Resultado base para todos los solvers."""
    
    success: bool
    challenge_type: Optional[ChallengeType] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class ClearanceResult(BaseResult):
    """Resultado específico para CF-Clearance."""
    
    clearance_cookie: Optional[Dict[str, Any]] = None
    all_cookies: Optional[list] = None
    challenge_detected: bool = False


@dataclass
class TurnstileResult(BaseResult):
    """Resultado específico para Turnstile."""
    
    token: Optional[str] = None
    sitekey: Optional[str] = None
    challenge_detected: bool = False


class SolverProtocol(Protocol):
    """Protocolo que define la interfaz común de los solvers."""
    
    async def start(self) -> None:
        """Inicializar el solver."""
        ...
    
    async def stop(self) -> None:
        """Detener el solver."""
        ...
    
    async def detect_challenge(self, url: str) -> Optional[ChallengeType]:
        """Detectar tipo de desafío en la URL."""
        ...


class BaseSolver(ABC):
    """
    Clase base abstracta para todos los solvers de Cloudflare.
    
    Proporciona funcionalidades comunes como configuración del navegador,
    gestión del contexto asíncrono y logging.
    
    Parameters
    ----------
    user_agent : Optional[str]
        User agent para el navegador.
    timeout : float
        Timeout en segundos.
    headless : bool
        Ejecutar en modo headless.
    proxy : Optional[str]
        Proxy a utilizar.
    """
    
    def __init__(
        self,
        *,
        user_agent: Optional[str] = None,
        timeout: float = 30.0,
        headless: bool = False,
        proxy: Optional[str] = None,
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent or get_chrome_user_agent()
        self._config = self._build_config(
            user_agent=self._user_agent,
            headless=headless,
            proxy=proxy,
        )
        self.driver: Optional[zendriver.Browser] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def _build_config(
        self,
        *,
        user_agent: str,
        headless: bool,
        proxy: Optional[str],
    ) -> zendriver.Config:
        """Construye la configuración del navegador."""
        config = zendriver.Config(headless=headless)
        config.add_argument(f"--user-agent={user_agent}")
        
        # Configurar proxy si se proporciona
        if proxy:
            auth_proxy = SeleniumAuthenticatedProxy(proxy)
            auth_proxy.enrich_chrome_options(config)
        
        return config

    async def __aenter__(self) -> "BaseSolver":
        """Inicializar el contexto asíncrono."""
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Limpiar el contexto asíncrono."""
        await self.stop()

    async def start(self) -> None:
        """Inicializar el navegador."""
        if self.driver is None:
            self.driver = zendriver.Browser(self._config)
            await self.driver.start()
            self._logger.debug("Navegador iniciado")

    async def stop(self) -> None:
        """Detener el navegador."""
        if self.driver is not None:
            await self.driver.stop()
            self.driver = None
            self._logger.debug("Navegador detenido")

    async def navigate_to(self, url: str) -> None:
        """Navega a la URL especificada."""
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        
        self._logger.info(f"Navegando a {url}")
        await self.driver.get(url)

    async def get_page_content(self) -> str:
        """Obtiene el contenido HTML de la página actual."""
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        return await self.driver.main_tab.get_content()

    async def get_current_user_agent(self) -> str:
        """Obtiene el user agent actual del navegador."""
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        return await self.driver.main_tab.evaluate("navigator.userAgent")

    @property
    def timeout(self) -> float:
        """Timeout configurado."""
        return self._timeout

    @property
    def user_agent(self) -> str:
        """User agent configurado."""
        return self._user_agent

    @abstractmethod
    async def detect_challenge(self, url: str) -> Optional[ChallengeType]:
        """Detecta el tipo de desafío en la URL especificada."""
        pass

    @abstractmethod
    async def solve(self, url: str, **kwargs: Any) -> BaseResult:
        """Resuelve el desafío en la URL especificada."""
        pass


class UnifiedCloudflareDetector:
    """
    Detector unificado para todos los tipos de desafíos de Cloudflare.
    
    Puede detectar tanto desafíos de clearance como Turnstile en una sola página.
    """
    
    @staticmethod
    async def detect_all_challenges(solver: BaseSolver, url: str) -> Dict[str, Any]:
        """
        Detecta todos los tipos de desafíos en una página.
        
        Parameters
        ----------
        solver : BaseSolver
            Instancia del solver para usar el navegador.
        url : str
            URL a analizar.
            
        Returns
        -------
        Dict[str, Any]
            Información sobre todos los desafíos detectados.
        """
        if solver.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        
        await solver.navigate_to(url)
        html_content = await solver.get_page_content()
        
        result = {
            "url": url,
            "challenges_found": [],
            "clearance": {"detected": False, "type": None},
            "turnstile": {"detected": False, "sitekey": None},
        }
        
        # Detectar desafíos de clearance
        clearance_patterns = [
            ("cType: 'non-interactive'", ChallengeType.JAVASCRIPT),
            ("cType: 'managed'", ChallengeType.MANAGED),
            ("cType: 'interactive'", ChallengeType.INTERACTIVE),
        ]
        
        for pattern, challenge_type in clearance_patterns:
            if pattern in html_content:
                result["clearance"]["detected"] = True
                result["clearance"]["type"] = challenge_type.value
                result["challenges_found"].append(challenge_type.value)
                break
        
        # Detectar Turnstile
        try:
            turnstile_elements = await solver.driver.main_tab.select_all('.cf-turnstile')
            for element in turnstile_elements:
                sitekey = await element.get_attribute('data-sitekey')
                if sitekey:
                    result["turnstile"]["detected"] = True
                    result["turnstile"]["sitekey"] = sitekey
                    result["challenges_found"].append("turnstile")
                    break
        except Exception as e:
            logger.debug(f"Error detectando Turnstile: {e}")
        
        return result
