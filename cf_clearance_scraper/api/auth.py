"""
Sistema de autenticación por API Key para CF-Clearance API.

Proporciona middleware de seguridad, validación de tokens y rate limiting.
"""

import hashlib
import time
from typing import Dict, Optional, Set
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

# Configuración de API Keys (en producción usar variables de entorno)
API_KEYS = {
    # Formato: "hashed_key": {"name": "client_name", "rate_limit": requests_per_minute}
    "d4c74594d841139328695756648b6bd6": {"name": "admin", "rate_limit": 1000},  # admin123
    "5e884898da28047151d0e56f8dc6292": {"name": "client1", "rate_limit": 100},   # hello456
    "ef92b778bafe771e89245b89ecbc08a": {"name": "client2", "rate_limit": 50},    # test789
}

# Rate limiting storage (en producción usar Redis)
rate_limit_storage: Dict[str, Dict[str, int]] = {}

# Security scheme
security = HTTPBearer()


def hash_api_key(api_key: str) -> str:
    """Genera hash MD5 de una API key."""
    return hashlib.md5(api_key.encode()).hexdigest()


def validate_api_key(api_key: str) -> Optional[Dict]:
    """
    Valida una API key y retorna información del cliente.
    
    Args:
        api_key: La API key a validar
        
    Returns:
        Dict con información del cliente o None si es inválida
    """
    hashed_key = hash_api_key(api_key)
    return API_KEYS.get(hashed_key)


def check_rate_limit(api_key: str, rate_limit: int) -> bool:
    """
    Verifica si el cliente ha excedido su rate limit.
    
    Args:
        api_key: La API key del cliente
        rate_limit: Límite de requests por minuto
        
    Returns:
        True si está dentro del límite, False si lo excede
    """
    current_minute = int(time.time() // 60)
    
    if api_key not in rate_limit_storage:
        rate_limit_storage[api_key] = {}
    
    # Limpiar minutos antiguos
    old_minutes = [minute for minute in rate_limit_storage[api_key].keys() 
                   if minute < current_minute - 1]
    for old_minute in old_minutes:
        del rate_limit_storage[api_key][old_minute]
    
    # Contar requests en el minuto actual
    current_requests = rate_limit_storage[api_key].get(current_minute, 0)
    
    if current_requests >= rate_limit:
        return False
    
    # Incrementar contador
    rate_limit_storage[api_key][current_minute] = current_requests + 1
    return True


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
    """
    Dependency para autenticar requests de la API.
    
    Args:
        credentials: Credenciales HTTP Bearer
        
    Returns:
        Dict con información del cliente autenticado
        
    Raises:
        HTTPException: Si la autenticación falla
    """
    api_key = credentials.credentials
    
    # Validar API key
    client_info = validate_api_key(api_key)
    if not client_info:
        logger.warning(f"API key inválida intentada: {api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar rate limit
    if not check_rate_limit(api_key, client_info["rate_limit"]):
        logger.warning(f"Rate limit excedido para cliente: {client_info['name']}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit excedido. Máximo {client_info['rate_limit']} requests por minuto.",
        )
    
    logger.info(f"Request autenticado para cliente: {client_info['name']}")
    return client_info


def generate_new_api_key() -> str:
    """
    Genera una nueva API key segura.
    
    Returns:
        API key de 32 caracteres
    """
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


def add_api_key(name: str, rate_limit: int = 100) -> str:
    """
    Añade una nueva API key al sistema.
    
    Args:
        name: Nombre del cliente
        rate_limit: Límite de requests por minuto
        
    Returns:
        La API key generada
    """
    api_key = generate_new_api_key()
    hashed_key = hash_api_key(api_key)
    
    API_KEYS[hashed_key] = {
        "name": name,
        "rate_limit": rate_limit
    }
    
    logger.info(f"Nueva API key creada para cliente: {name}")
    return api_key


def revoke_api_key(api_key: str) -> bool:
    """
    Revoca una API key existente.
    
    Args:
        api_key: La API key a revocar
        
    Returns:
        True si se revocó exitosamente, False si no existía
    """
    hashed_key = hash_api_key(api_key)
    
    if hashed_key in API_KEYS:
        client_name = API_KEYS[hashed_key]["name"]
        del API_KEYS[hashed_key]
        logger.info(f"API key revocada para cliente: {client_name}")
        return True
    
    return False


def get_usage_stats() -> Dict:
    """
    Obtiene estadísticas de uso de la API.
    
    Returns:
        Dict con estadísticas por cliente
    """
    current_minute = int(time.time() // 60)
    stats = {}
    
    for api_key, minutes_data in rate_limit_storage.items():
        # Encontrar cliente por API key
        hashed_key = None
        for hashed, info in API_KEYS.items():
            if hash_api_key(api_key) == hashed:
                hashed_key = hashed
                break
        
        if hashed_key:
            client_info = API_KEYS[hashed_key]
            current_usage = minutes_data.get(current_minute, 0)
            
            stats[client_info["name"]] = {
                "current_minute_requests": current_usage,
                "rate_limit": client_info["rate_limit"],
                "usage_percentage": (current_usage / client_info["rate_limit"]) * 100
            }
    
    return stats

