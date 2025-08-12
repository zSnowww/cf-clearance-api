"""Modelos de datos para la API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, HttpUrl, Field
from zendriver.cdp.network import T_JSON_DICT


class ScrapeRequest(BaseModel):
    """Modelo de solicitud para scraping."""
    
    url: HttpUrl = Field(..., description="URL objetivo para scraping")
    user_agent: Optional[str] = Field(None, description="User agent personalizado")
    timeout: float = Field(30.0, gt=0, le=300, description="Timeout en segundos")
    proxy: Optional[str] = Field(None, description="URL del proxy")
    headless: bool = Field(True, description="Ejecutar en modo headless")
    http2: bool = Field(True, description="Habilitar HTTP/2")
    http3: bool = Field(True, description="Habilitar HTTP/3")


class ScrapeResponse(BaseModel):
    """Modelo de respuesta exitosa."""
    
    success: bool = Field(True, description="Indica si la operación fue exitosa")
    clearance_cookie: T_JSON_DICT = Field(..., description="Cookie cf_clearance obtenida")
    all_cookies: List[T_JSON_DICT] = Field(..., description="Todas las cookies obtenidas")
    user_agent: str = Field(..., description="User agent usado")
    challenge_detected: Optional[str] = Field(None, description="Tipo de desafío detectado")
    processing_time: float = Field(..., description="Tiempo de procesamiento en segundos")


class ErrorResponse(BaseModel):
    """Modelo de respuesta de error."""
    
    success: bool = Field(False, description="Indica que la operación falló")
    error: str = Field(..., description="Mensaje de error")
    error_code: str = Field(..., description="Código de error")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalles adicionales del error")


class CookieRecord(BaseModel):
    """Modelo para registro de cookie guardado."""
    
    unix_timestamp: int = Field(..., description="Timestamp Unix")
    timestamp: str = Field(..., description="Timestamp ISO")
    cf_clearance: str = Field(..., description="Valor de la cookie cf_clearance")
    cookies: List[T_JSON_DICT] = Field(..., description="Todas las cookies")
    user_agent: str = Field(..., description="User agent usado")
    proxy: Optional[str] = Field(None, description="Proxy usado")
    created_at: str = Field(..., description="Timestamp de creación")


class HealthResponse(BaseModel):
    """Modelo de respuesta de health check."""
    
    status: str = Field("healthy", description="Estado del servicio")
    version: str = Field(..., description="Versión del servicio")
    uptime_seconds: float = Field(..., description="Tiempo de funcionamiento en segundos")
    uptime_formatted: str = Field(..., description="Tiempo de funcionamiento formateado")


class TurnstileRequest(BaseModel):
    """Modelo de solicitud para Turnstile."""
    
    url: HttpUrl = Field(..., description="URL donde está el desafío de Turnstile")
    sitekey: Optional[str] = Field(None, description="Sitekey manual (opcional para detección automática)")
    mode: str = Field("auto_detect", description="Modo: 'auto_detect' o 'manual'")
    action: Optional[str] = Field(None, description="Parámetro action del widget")
    cdata: Optional[str] = Field(None, description="Parámetro cdata del widget")
    user_agent: Optional[str] = Field(None, description="User agent personalizado")
    timeout: float = Field(30.0, gt=0, le=300, description="Timeout en segundos")
    proxy: Optional[str] = Field(None, description="URL del proxy")
    headless: bool = Field(False, description="No ejecutar en modo headless")


class TurnstileResponse(BaseModel):
    """Modelo de respuesta de Turnstile."""
    
    success: bool = Field(..., description="Indica si la resolución fue exitosa")
    token: Optional[str] = Field(None, description="Token de Turnstile obtenido")
    sitekey: Optional[str] = Field(None, description="Sitekey usado o detectado")
    processing_time: float = Field(..., description="Tiempo de procesamiento en segundos")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falla")
    challenge_detected: bool = Field(False, description="Si se detectó un desafío")
    mode_used: str = Field(..., description="Modo usado para la resolución") 