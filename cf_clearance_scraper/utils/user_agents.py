"""Utilidades para manejo de user agents."""

from __future__ import annotations

import random
from typing import List

import latest_user_agents


def get_chrome_user_agent() -> str:
    """
    Obtiene un user agent aleatorio y actualizado de Chrome.
    
    Returns
    -------
    str
        Un user agent de Chrome seleccionado aleatoriamente.
        
    Raises
    ------
    ValueError
        Si no se encuentran user agents de Chrome disponibles.
    """
    chrome_user_agents: List[str] = [
        user_agent
        for user_agent in latest_user_agents.get_latest_user_agents()
        if "Chrome" in user_agent and "Edg" not in user_agent
    ]
    
    if not chrome_user_agents:
        raise ValueError("No se encontraron user agents de Chrome disponibles")
    
    return random.choice(chrome_user_agents)


def is_chrome_user_agent(user_agent: str) -> bool:
    """
    Verifica si un user agent corresponde a Chrome.
    
    Parameters
    ----------
    user_agent : str
        El user agent a verificar.
        
    Returns
    -------
    bool
        True si es un user agent de Chrome, False en caso contrario.
    """
    return "Chrome" in user_agent and "Edg" not in user_agent 