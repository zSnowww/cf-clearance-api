"""Utilidades para almacenamiento de datos."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from zendriver.cdp.network import T_JSON_DICT

logger = logging.getLogger(__name__)


def write_cookie_record(
    *,
    output_path: str | Path,
    clearance_cookie: T_JSON_DICT,
    all_cookies: List[T_JSON_DICT],
    user_agent: str,
    proxy: Optional[str] = None,
) -> None:
    """
    Escribe un registro de cookie y metadatos en JSON, agrupado por dominio.
    
    Parameters
    ----------
    output_path : str | Path
        Ruta del archivo donde guardar los datos.
    clearance_cookie : T_JSON_DICT
        Cookie de clearance de Cloudflare.
    all_cookies : List[T_JSON_DICT]
        Lista completa de cookies.
    user_agent : str
        User agent usado.
    proxy : Optional[str]
        Proxy usado, si aplica.
    """
    output_path = Path(output_path)
    logger.info(f"Escribiendo información de cookies a {output_path}")

    # Cargar datos existentes o crear estructura nueva
    json_data: Dict[str, List[Dict[str, Any]]] = {}
    if output_path.exists():
        try:
            with output_path.open(encoding="utf-8") as file:
                json_data = json.load(file)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Error leyendo archivo existente: {e}")

    # Calcular timestamps
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    unix_timestamp = clearance_cookie["expires"] - timedelta(days=365).total_seconds()
    timestamp = datetime.fromtimestamp(unix_timestamp, tz=local_timezone).isoformat()

    # Preparar registro
    domain_key = clearance_cookie["domain"]
    record = {
        "unix_timestamp": int(unix_timestamp),
        "timestamp": timestamp,
        "cf_clearance": clearance_cookie["value"],
        "cookies": all_cookies,
        "user_agent": user_agent,
        "proxy": proxy,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Agregar al dominio correspondiente
    json_data.setdefault(domain_key, []).append(record)

    # Guardar archivo
    try:
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(json_data, file, indent=4, ensure_ascii=False)
        logger.info(f"Datos guardados exitosamente en {output_path}")
    except OSError as e:
        logger.error(f"Error escribiendo archivo: {e}")
        raise


def load_cookie_records(file_path: str | Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Carga registros de cookies desde un archivo JSON.
    
    Parameters
    ----------
    file_path : str | Path
        Ruta del archivo a cargar.
        
    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        Datos de cookies agrupados por dominio.
        
    Raises
    ------
    FileNotFoundError
        Si el archivo no existe.
    json.JSONDecodeError
        Si el archivo no es JSON válido.
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    
    with file_path.open(encoding="utf-8") as file:
        return json.load(file)


def get_latest_record(
    records: Dict[str, List[Dict[str, Any]]], 
    domain: str
) -> Optional[Dict[str, Any]]:
    """
    Obtiene el registro más reciente para un dominio.
    
    Parameters
    ----------
    records : Dict[str, List[Dict[str, Any]]]
        Registros de cookies.
    domain : str
        Dominio a buscar.
        
    Returns
    -------
    Optional[Dict[str, Any]]
        El registro más reciente o None si no existe.
    """
    domain_records = records.get(domain, [])
    if not domain_records:
        return None
    
    # Ordenar por timestamp y tomar el más reciente
    sorted_records = sorted(
        domain_records, 
        key=lambda x: x.get("unix_timestamp", 0), 
        reverse=True
    )
    return sorted_records[0]


def cleanup_expired_records(
    records: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Limpia registros expirados de la estructura de datos.
    
    Parameters
    ----------
    records : Dict[str, List[Dict[str, Any]]]
        Registros de cookies.
        
    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        Registros filtrados sin los expirados.
    """
    current_time = datetime.now(timezone.utc).timestamp()
    cleaned_records = {}
    
    for domain, domain_records in records.items():
        valid_records = [
            record for record in domain_records
            if record.get("unix_timestamp", 0) > current_time
        ]
        if valid_records:
            cleaned_records[domain] = valid_records
    
    return cleaned_records 