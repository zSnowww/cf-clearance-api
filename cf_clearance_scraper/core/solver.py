"""
Solver de desafíos de Cloudflare para obtener cookies cf_clearance.

Este módulo contiene la lógica principal para detectar y resolver
desafíos de clearance de Cloudflare usando Zendriver.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Iterable, List, Optional

import user_agents
from zendriver import cdp
from zendriver.cdp.emulation import UserAgentBrandVersion, UserAgentMetadata
from zendriver.cdp.network import T_JSON_DICT, Cookie
from zendriver.core.element import Element

from .base import BaseSolver, ChallengeType, ClearanceResult

logger = logging.getLogger(__name__)

# Mapeo de tipos de desafío a mensajes
CHALLENGE_MESSAGES = {
    ChallengeType.JAVASCRIPT: "Solving Cloudflare challenge [JavaScript]...",
    ChallengeType.MANAGED: "Solving Cloudflare challenge [Managed]...",
    ChallengeType.INTERACTIVE: "Solving Cloudflare challenge [Interactive]...",
}

# Mantener compatibilidad hacia atrás
class ChallengePlatform:
    """Clase de compatibilidad para ChallengePlatform."""
    JAVASCRIPT = ChallengeType.JAVASCRIPT
    MANAGED = ChallengeType.MANAGED
    INTERACTIVE = ChallengeType.INTERACTIVE


class CloudflareSolver(BaseSolver):
    """
    Solver para desafíos de clearance de Cloudflare.

    Parameters
    ----------
    user_agent : Optional[str]
        User agent para el navegador.
    timeout : float
        Timeout en segundos para acciones del navegador y resolución de desafíos.
    http2 : bool
        Habilitar/deshabilitar HTTP/2.
    http3 : bool
        Habilitar/deshabilitar HTTP/3.
    headless : bool
        Ejecutar en modo headless.
    proxy : Optional[str]
        Proxy a utilizar en las peticiones del navegador.
    """

    def __init__(
        self,
        *,
        user_agent: Optional[str] = None,
        timeout: float = 30.0,
        http2: bool = True,
        http3: bool = True,
        headless: bool = False,
        proxy: Optional[str] = None,
    ) -> None:
        # Llamar al constructor base
        super().__init__(
            user_agent=user_agent,
            timeout=timeout,
            headless=headless,
            proxy=proxy,
        )
        
        # Configuraciones específicas de CloudflareSolver
        self._http2 = http2
        self._http3 = http3
        self._update_config_for_http()

    def _update_config_for_http(self) -> None:
        """Actualiza la configuración para HTTP/2 y HTTP/3."""
        if not self._http2:
            self._config.add_argument("--disable-http2")
        if not self._http3:
            self._config.add_argument("--disable-quic")

    # -----------------------------
    # Utilidades de cookies
    # -----------------------------
    @staticmethod
    def _format_cookies(cookies: Iterable[Cookie]) -> List[T_JSON_DICT]:
        """Formatea cookies a una lista de JSON cookies."""
        return [cookie.to_json() for cookie in cookies]

    @staticmethod
    def extract_clearance_cookie(
        cookies: Iterable[T_JSON_DICT],
    ) -> Optional[T_JSON_DICT]:
        """Extrae la cookie de Cloudflare `cf_clearance` de una lista de cookies."""
        for cookie in cookies:
            if cookie["name"] == "cf_clearance":
                return cookie
        return None

    async def get_cookies(self) -> List[T_JSON_DICT]:
        """Obtiene todas las cookies de la página actual."""
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        return self._format_cookies(await self.driver.cookies.get_all())

    async def set_user_agent_metadata(self, user_agent: str) -> None:
        """Establece metadatos del user agent vía CDP para mimetizar Chrome real."""
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
            
        device = user_agents.parse(user_agent)

        metadata = UserAgentMetadata(
            architecture="x86",
            bitness="64",
            brands=[
                UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
                UserAgentBrandVersion(
                    brand="Chromium", version=str(device.browser.version[0])
                ),
                UserAgentBrandVersion(
                    brand="Google Chrome",
                    version=str(device.browser.version[0]),
                ),
            ],
            full_version_list=[
                UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
                UserAgentBrandVersion(
                    brand="Chromium", version=str(device.browser.version[0])
                ),
                UserAgentBrandVersion(
                    brand="Google Chrome",
                    version=str(device.browser.version[0]),
                ),
            ],
            mobile=device.is_mobile,
            model=device.device.model or "",
            platform=device.os.family,
            platform_version=device.os.version_string,
            full_version=device.browser.version_string,
            wow64=False,
        )

        self.driver.main_tab.feed_cdp(
            cdp.network.set_user_agent_override(
                user_agent, user_agent_metadata=metadata
            )
        )

    # -----------------------------
    # Detección y resolución de desafío
    # -----------------------------
    async def detect_challenge(self, url: Optional[str] = None) -> Optional[ChallengeType]:
        """Detecta el tipo de desafío de Cloudflare en la página actual o URL especificada."""
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        
        if url:
            await self.navigate_to(url)
            
        html = await self.get_page_content()
        
        # Detectar tipos de desafío de clearance
        challenge_patterns = [
            ("cType: 'non-interactive'", ChallengeType.JAVASCRIPT),
            ("cType: 'managed'", ChallengeType.MANAGED), 
            ("cType: 'interactive'", ChallengeType.INTERACTIVE),
        ]
        
        for pattern, challenge_type in challenge_patterns:
            if pattern in html:
                self._logger.debug(f"Desafío detectado: {challenge_type.value}")
                return challenge_type
        
        return None

    async def solve_challenge(self) -> bool:
        """
        Resuelve el desafío de Cloudflare en la página actual.
        
        Returns
        -------
        bool
            True si el desafío fue resuelto exitosamente, False en caso contrario.
        """
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
            
        start_timestamp = datetime.now()
        logger.info("Iniciando resolución del desafío")

        while (
            self.extract_clearance_cookie(await self.get_cookies()) is None
            and await self.detect_challenge() is not None
            and (datetime.now() - start_timestamp).seconds < self._timeout
        ):
            try:
                widget_input = await self.driver.main_tab.find("input")

                if widget_input.parent is None or not widget_input.parent.shadow_roots:
                    await asyncio.sleep(0.25)
                    continue

                challenge = Element(
                    widget_input.parent.shadow_roots[0],
                    self.driver.main_tab,
                    widget_input.parent.tree,
                )

                challenge = challenge.children[0]

                if (
                    isinstance(challenge, Element)
                    and "display: none;" not in challenge.attrs.get("style", "")
                ):
                    await asyncio.sleep(1)

                    try:
                        await challenge.get_position()
                        await challenge.mouse_click()
                        logger.debug("Click en el desafío realizado")
                    except Exception as e:
                        logger.debug(f"Error al hacer click: {e}")
                        continue

            except Exception as e:
                logger.debug(f"Error durante la resolución: {e}")
                await asyncio.sleep(0.5)

        # Verificar si se resolvió
        final_cookies = await self.get_cookies()
        success = self.extract_clearance_cookie(final_cookies) is not None
        
        if success:
            logger.info("Desafío resuelto exitosamente")
        else:
            logger.warning("No se pudo resolver el desafío")
            
        return success

    async def solve(self, url: str, **kwargs: Any) -> ClearanceResult:
        """
        Método principal para resolver desafíos de clearance.
        
        Parameters
        ----------
        url : str
            URL objetivo.
        **kwargs
            Argumentos adicionales.
            
        Returns
        -------
        ClearanceResult
            Resultado de la resolución.
        """
        start_time = time.time()
        
        try:
            await self.navigate_to(url)
            all_cookies = await self.get_cookies()
            clearance_cookie = self.extract_clearance_cookie(all_cookies)
            
            challenge_type = None
            challenge_detected = False
            
            if clearance_cookie is None:
                challenge_type = await self.detect_challenge()
                
                if challenge_type is None:
                    return ClearanceResult(
                        success=False,
                        error_message="No se detectó desafío de Cloudflare y no hay cookie de clearance",
                        processing_time=time.time() - start_time,
                        url=url,
                        user_agent=self.user_agent,
                    )
                
                challenge_detected = True
                self._logger.info(CHALLENGE_MESSAGES[challenge_type])
                
                # Configurar metadatos del user agent para parecer más real
                await self.set_user_agent_metadata(await self.get_current_user_agent())
                
                # Intentar resolver el desafío
                success = await self.solve_challenge()
                
                if not success:
                    return ClearanceResult(
                        success=False,
                        challenge_type=challenge_type,
                        error_message="No se pudo resolver el desafío de Cloudflare",
                        processing_time=time.time() - start_time,
                        url=url,
                        user_agent=self.user_agent,
                        challenge_detected=True,
                    )
                
                # Obtener cookies después de resolver
                all_cookies = await self.get_cookies()
                clearance_cookie = self.extract_clearance_cookie(all_cookies)
                
                if clearance_cookie is None:
                    return ClearanceResult(
                        success=False,
                        challenge_type=challenge_type,
                        error_message="No se obtuvo cookie de clearance después de resolver el desafío",
                        processing_time=time.time() - start_time,
                        url=url,
                        user_agent=self.user_agent,
                        challenge_detected=True,
                    )
            
            return ClearanceResult(
                success=True,
                challenge_type=challenge_type,
                clearance_cookie=clearance_cookie,
                all_cookies=all_cookies,
                processing_time=time.time() - start_time,
                url=url,
                user_agent=await self.get_current_user_agent(),
                challenge_detected=challenge_detected,
            )
            
        except Exception as e:
            self._logger.error(f"Error resolviendo desafío: {e}")
            return ClearanceResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time,
                url=url,
                user_agent=self.user_agent,
            ) 