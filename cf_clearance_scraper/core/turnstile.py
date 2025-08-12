"""
Solver de Turnstile de Cloudflare.

Este módulo contiene la lógica para detectar automáticamente sitekeys
y resolver desafíos de Turnstile usando Zendriver.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional, Any

from .base import BaseSolver, ChallengeType, TurnstileResult, SolverMode

logger = logging.getLogger(__name__)

# Mantener compatibilidad hacia atrás
class TurnstileMode:
    """Clase de compatibilidad para TurnstileMode."""
    AUTO_DETECT = SolverMode.AUTO_DETECT
    MANUAL = SolverMode.MANUAL


class TurnstileSolver(BaseSolver):
    """
    Solver para desafíos de Turnstile de Cloudflare.
    
    Soporta detección automática de sitekey y resolución del desafío.
    Hereda de BaseSolver para funcionalidades comunes.
    
    Parameters
    ----------
    user_agent : Optional[str]
        User agent para el navegador.
    timeout : float
        Timeout en segundos para la resolución.
    headless : bool
        Ejecutar en modo headless.
    proxy : Optional[str]
        Proxy a utilizar.
    """
    
    # Plantilla HTML para el widget de Turnstile
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Turnstile Solver</title>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    </head>
    <body>
        <div id="turnstile-widget" class="cf-turnstile" data-sitekey="{sitekey}" 
             data-callback="onTurnstileSuccess" data-error-callback="onTurnstileError"></div>
        
        <script>
            window.turnstileResult = null;
            window.turnstileError = null;
            
            function onTurnstileSuccess(token) {{
                window.turnstileResult = token;
                console.log('Turnstile success:', token);
            }}
            
            function onTurnstileError(error) {{
                window.turnstileError = error;
                console.log('Turnstile error:', error);
            }}
        </script>
    </body>
    </html>
    """
    
    # Patrón regex para sitekeys de Turnstile
    SITEKEY_PATTERN = re.compile(r'[0-9]x[A-Fa-f0-9]{20,22}')

    async def detect_challenge(self, url: Optional[str] = None) -> Optional[ChallengeType]:
        """
        Detecta si hay un desafío de Turnstile en la página.
        
        Parameters
        ----------
        url : Optional[str]
            URL a verificar (si no se proporciona, usa la página actual).
            
        Returns
        -------
        Optional[ChallengeType]
            ChallengeType.TURNSTILE si se detecta, None en caso contrario.
        """
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        
        if url:
            await self.navigate_to(url)
        
        try:
            # Buscar elementos con la clase cf-turnstile
            turnstile_elements = await self.driver.main_tab.select_all('.cf-turnstile')
            
            for element in turnstile_elements:
                sitekey = await element.get_attribute('data-sitekey')
                if sitekey and self._validate_sitekey(sitekey):
                    self._logger.debug("Desafío de Turnstile detectado")
                    return ChallengeType.TURNSTILE
            
            # Buscar en el HTML completo como fallback
            html_content = await self.get_page_content()
            if self.SITEKEY_PATTERN.search(html_content):
                self._logger.debug("Turnstile detectado en HTML")
                return ChallengeType.TURNSTILE
                
        except Exception as e:
            self._logger.debug(f"Error detectando Turnstile: {e}")
        
        return None

    async def detect_sitekey(self, url: str) -> Optional[str]:
        """
        Detecta automáticamente el sitekey de Turnstile en una página.
        
        Parameters
        ----------
        url : str
            URL de la página a analizar.
            
        Returns
        -------
        Optional[str]
            Sitekey detectado o None si no se encuentra.
        """
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        
        self._logger.info(f"Detectando sitekey en {url}")
        
        try:
            await self.navigate_to(url)
            
            # Buscar elementos con la clase cf-turnstile
            turnstile_elements = await self.driver.main_tab.select_all('.cf-turnstile')
            
            for element in turnstile_elements:
                sitekey = await element.get_attribute('data-sitekey')
                if sitekey and self._validate_sitekey(sitekey):
                    self._logger.info(f"Sitekey detectado: {sitekey}")
                    return sitekey
            
            # Buscar en el HTML completo como fallback
            html_content = await self.get_page_content()
            sitekey_matches = self.SITEKEY_PATTERN.findall(html_content)
            
            for match in sitekey_matches:
                if self._validate_sitekey(match):
                    self._logger.info(f"Sitekey detectado en HTML: {match}")
                    return match
            
            self._logger.warning("No se encontró sitekey en la página")
            return None
            
        except Exception as e:
            self._logger.error(f"Error detectando sitekey: {e}")
            return None

    def _validate_sitekey(self, sitekey: str) -> bool:
        """
        Valida el formato de un sitekey de Turnstile.
        
        Parameters
        ----------
        sitekey : str
            Sitekey a validar.
            
        Returns
        -------
        bool
            True si el formato es válido.
        """
        if not sitekey:
            return False
        
        # Verificar patrón: [número]x[hexadecimal de 20-22 caracteres]
        return bool(self.SITEKEY_PATTERN.match(sitekey))

    async def solve(self, url: str, **kwargs: Any) -> TurnstileResult:
        """
        Método principal para resolver desafíos de Turnstile.
        
        Parameters
        ----------
        url : str
            URL objetivo.
        **kwargs
            Argumentos adicionales: sitekey, mode, action, cdata.
            
        Returns
        -------
        TurnstileResult
            Resultado de la resolución.
        """
        sitekey = kwargs.get('sitekey')
        mode = kwargs.get('mode', SolverMode.AUTO_DETECT)
        action = kwargs.get('action')
        cdata = kwargs.get('cdata')
        
        return await self.solve_turnstile(
            url=url,
            sitekey=sitekey,
            mode=mode,
            action=action,
            cdata=cdata,
        )

    async def solve_turnstile(
        self,
        url: str,
        sitekey: Optional[str] = None,
        mode: SolverMode = SolverMode.AUTO_DETECT,
        action: Optional[str] = None,
        cdata: Optional[str] = None,
    ) -> TurnstileResult:
        """
        Resuelve un desafío de Turnstile.
        
        Parameters
        ----------
        url : str
            URL donde está el desafío.
        sitekey : Optional[str]
            Sitekey manual (requerido si mode=MANUAL).
        mode : SolverMode
            Modo de detección de sitekey.
        action : Optional[str]
            Parámetro action del widget.
        cdata : Optional[str]
            Parámetro cdata del widget.
            
        Returns
        -------
        TurnstileResult
            Resultado de la resolución.
        """
        start_time = time.time()
        
        try:
            # Determinar sitekey según el modo
            if mode == SolverMode.AUTO_DETECT:
                detected_sitekey = await self.detect_sitekey(url)
                if not detected_sitekey:
                    return TurnstileResult(
                        success=False,
                        error_message="No se pudo detectar automáticamente el sitekey",
                        processing_time=time.time() - start_time,
                        url=url,
                        user_agent=self.user_agent,
                    )
                target_sitekey = detected_sitekey
            else:
                if not sitekey:
                    return TurnstileResult(
                        success=False,
                        error_message="Se requiere sitekey en modo manual",
                        processing_time=time.time() - start_time,
                        url=url,
                        user_agent=self.user_agent,
                    )
                if not self._validate_sitekey(sitekey):
                    return TurnstileResult(
                        success=False,
                        error_message=f"Formato de sitekey inválido: {sitekey}",
                        processing_time=time.time() - start_time,
                        url=url,
                        user_agent=self.user_agent,
                    )
                target_sitekey = sitekey
            
            self._logger.info(f"Resolviendo Turnstile con sitekey: {target_sitekey}")
            
            # Crear página personalizada con widget
            token = await self._solve_with_widget(
                url=url,
                sitekey=target_sitekey,
                action=action,
                cdata=cdata,
            )
            
            processing_time = time.time() - start_time
            
            if token:
                self._logger.info(f"Turnstile resuelto exitosamente en {processing_time:.2f}s")
                return TurnstileResult(
                    success=True,
                    challenge_type=ChallengeType.TURNSTILE,
                    token=token,
                    sitekey=target_sitekey,
                    processing_time=processing_time,
                    url=url,
                    user_agent=self.user_agent,
                    challenge_detected=True,
                )
            else:
                return TurnstileResult(
                    success=False,
                    challenge_type=ChallengeType.TURNSTILE,
                    sitekey=target_sitekey,
                    error_message="No se pudo obtener token de Turnstile",
                    processing_time=processing_time,
                    url=url,
                    user_agent=self.user_agent,
                    challenge_detected=True,
                )
                
        except Exception as e:
            self._logger.error(f"Error resolviendo Turnstile: {e}")
            return TurnstileResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time,
                url=url,
                user_agent=self.user_agent,
            )

    async def _solve_with_widget(
        self,
        *,
        url: str,
        sitekey: str,
        action: Optional[str] = None,
        cdata: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resuelve el desafío usando un widget personalizado.
        
        Parameters
        ----------
        url : str
            URL base.
        sitekey : str
            Sitekey del desafío.
        action : Optional[str]
            Parámetro action.
        cdata : Optional[str]
            Parámetro cdata.
            
        Returns
        -------
        Optional[str]
            Token de Turnstile o None si falla.
        """
        if self.driver is None:
            raise RuntimeError("El navegador no está iniciado")
        
        html_content = self.HTML_TEMPLATE.format(sitekey=sitekey)
        
        # Crear ruta temporal para servir el HTML
        test_url = f"{url.rstrip('/')}/turnstile-solver"
        
        try:
            # Configurar ruta para servir HTML personalizado
            await self.driver.main_tab.route(
                test_url,
                lambda route: route.fulfill(
                    body=html_content,
                    headers={"Content-Type": "text/html"}
                )
            )
            
            # Navegar a la página personalizada
            await self.driver.main_tab.goto(test_url)
            
            # Esperar a que el widget se cargue
            await asyncio.sleep(2)
            
            # Intentar resolver el desafío
            max_attempts = int(self.timeout)
            
            for attempt in range(max_attempts):
                try:
                    # Verificar si hay resultado exitoso
                    result = await self.driver.main_tab.evaluate("window.turnstileResult")
                    if result:
                        return result
                    
                    # Verificar si hay error
                    error = await self.driver.main_tab.evaluate("window.turnstileError")
                    if error:
                        self._logger.warning(f"Error de Turnstile: {error}")
                        break
                    
                    # Hacer click en el widget si está presente y visible
                    try:
                        widget = await self.driver.main_tab.select("#turnstile-widget")
                        if widget:
                            await widget.click()
                    except Exception:
                        pass
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self._logger.debug(f"Intento {attempt + 1} falló: {e}")
                    await asyncio.sleep(1)
            
            return None
            
        except Exception as e:
            self._logger.error(f"Error en resolución de widget: {e}")
            return None

    async def solve_auto(self, url: str) -> TurnstileResult:
        """
        Método de conveniencia para resolución automática.
        
        Parameters
        ----------
        url : str
            URL a procesar.
            
        Returns
        -------
        TurnstileResult
            Resultado de la resolución.
        """
        return await self.solve_turnstile(url, mode=SolverMode.AUTO_DETECT)

    async def solve_manual(
        self,
        url: str,
        sitekey: str,
        action: Optional[str] = None,
        cdata: Optional[str] = None,
    ) -> TurnstileResult:
        """
        Método de conveniencia para resolución manual.
        
        Parameters
        ----------
        url : str
            URL a procesar.
        sitekey : str
            Sitekey del desafío.
        action : Optional[str]
            Parámetro action.
        cdata : Optional[str]
            Parámetro cdata.
            
        Returns
        -------
        TurnstileResult
            Resultado de la resolución.
        """
        return await self.solve_turnstile(
            url=url,
            sitekey=sitekey,
            mode=SolverMode.MANUAL,
            action=action,
            cdata=cdata,
        )