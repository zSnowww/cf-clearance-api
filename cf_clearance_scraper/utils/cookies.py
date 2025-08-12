"""Utilidades para manejo de cookies."""

from __future__ import annotations

from typing import Iterable

from zendriver.cdp.network import T_JSON_DICT


def format_cookie_header(cookies: Iterable[T_JSON_DICT]) -> str:
    """
    Formatea cookies para un header Cookie HTTP.
    
    Parameters
    ----------
    cookies : Iterable[T_JSON_DICT]
        Lista de cookies en formato JSON.
        
    Returns
    -------
    str
        String formateado para header Cookie con formato 'name=value; name2=value2'.
    """
    return "; ".join(f'{cookie["name"]}={cookie["value"]}' for cookie in cookies)


def filter_domain_cookies(cookies: Iterable[T_JSON_DICT], domain: str) -> list[T_JSON_DICT]:
    """
    Filtra cookies por dominio específico.
    
    Parameters
    ----------
    cookies : Iterable[T_JSON_DICT]
        Lista de cookies a filtrar.
    domain : str
        Dominio por el cual filtrar.
        
    Returns
    -------
    list[T_JSON_DICT]
        Lista de cookies que pertenecen al dominio especificado.
    """
    return [
        cookie for cookie in cookies 
        if cookie.get("domain", "").endswith(domain)
    ]


def get_cookie_by_name(cookies: Iterable[T_JSON_DICT], name: str) -> T_JSON_DICT | None:
    """
    Busca una cookie específica por nombre.
    
    Parameters
    ----------
    cookies : Iterable[T_JSON_DICT]
        Lista de cookies donde buscar.
    name : str
        Nombre de la cookie a buscar.
        
    Returns
    -------
    T_JSON_DICT | None
        La cookie encontrada o None si no existe.
    """
    for cookie in cookies:
        if cookie.get("name") == name:
            return cookie
    return None 