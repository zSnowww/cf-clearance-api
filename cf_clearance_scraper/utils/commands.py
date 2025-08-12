"""Utilidades para generar comandos HTTP."""

from __future__ import annotations

from typing import Final, Optional

COMMAND_TEMPLATE: Final[str] = (
    '{name}: {binary} --header "Cookie: {cookies}" --header "User-Agent: {user_agent}" {url}'
)


def compute_tool_url_arg(tool: str, url: str, proxy: Optional[str] = None) -> str:
    """
    Computa el argumento de URL según la herramienta y proxy.
    
    Parameters
    ----------
    tool : str
        Nombre de la herramienta (curl, wget, aria2).
    url : str
        URL objetivo.
    proxy : Optional[str]
        URL del proxy a usar.
        
    Returns
    -------
    str
        Argumento de URL formateado para la herramienta especificada.
    """
    tool_lower = tool.lower()
    
    if tool_lower == "curl" and proxy is not None:
        return f"--proxy {proxy} {url}"
    elif tool_lower == "aria2" and proxy is not None:
        return f"--all-proxy {proxy} {url}"
    else:
        # wget maneja proxy por variables de entorno/config
        return url


def render_http_command(
    *,
    tool_name: str,
    binary: str,
    cookies_header: str,
    user_agent: str,
    url_arg: str,
) -> str:
    """
    Renderiza un comando HTTP completo.
    
    Parameters
    ----------
    tool_name : str
        Nombre descriptivo de la herramienta.
    binary : str
        Nombre del binario ejecutable.
    cookies_header : str
        Header de cookies formateado.
    user_agent : str
        User agent a usar.
    url_arg : str
        Argumento de URL (puede incluir flags de proxy).
        
    Returns
    -------
    str
        Comando HTTP completo listo para ejecutar.
    """
    return COMMAND_TEMPLATE.format(
        name=tool_name,
        binary=binary,
        cookies=cookies_header,
        user_agent=user_agent,
        url=url_arg,
    )


def generate_curl_command(
    *,
    url: str,
    cookies_header: str,
    user_agent: str,
    proxy: Optional[str] = None,
) -> str:
    """
    Genera un comando cURL específico.
    
    Parameters
    ----------
    url : str
        URL objetivo.
    cookies_header : str
        Header de cookies.
    user_agent : str
        User agent.
    proxy : Optional[str]
        Proxy a usar.
        
    Returns
    -------
    str
        Comando cURL completo.
    """
    url_arg = compute_tool_url_arg("curl", url, proxy)
    return render_http_command(
        tool_name="cURL",
        binary="curl",
        cookies_header=cookies_header,
        user_agent=user_agent,
        url_arg=url_arg,
    )


def generate_wget_command(
    *,
    url: str,
    cookies_header: str,
    user_agent: str,
) -> str:
    """
    Genera un comando wget específico.
    
    Note: wget maneja proxies por variables de entorno o archivo de config.
    
    Parameters
    ----------
    url : str
        URL objetivo.
    cookies_header : str
        Header de cookies.
    user_agent : str
        User agent.
        
    Returns
    -------
    str
        Comando wget completo.
    """
    return render_http_command(
        tool_name="Wget",
        binary="wget",
        cookies_header=cookies_header,
        user_agent=user_agent,
        url_arg=url,
    )


def generate_aria2_command(
    *,
    url: str,
    cookies_header: str,
    user_agent: str,
    proxy: Optional[str] = None,
) -> str:
    """
    Genera un comando aria2 específico.
    
    Parameters
    ----------
    url : str
        URL objetivo.
    cookies_header : str
        Header de cookies.
    user_agent : str
        User agent.
    proxy : Optional[str]
        Proxy a usar (SOCKS no soportado).
        
    Returns
    -------
    str
        Comando aria2 completo.
    """
    url_arg = compute_tool_url_arg("aria2", url, proxy)
    return render_http_command(
        tool_name="aria2",
        binary="aria2c",
        cookies_header=cookies_header,
        user_agent=user_agent,
        url_arg=url_arg,
    ) 