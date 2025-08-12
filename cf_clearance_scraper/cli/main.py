"""Módulo principal del CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Optional, Tuple, List

from zendriver.cdp.network import T_JSON_DICT

from cf_clearance_scraper.core import CloudflareSolver, ChallengePlatform, ChallengeType
from cf_clearance_scraper.utils.user_agents import get_chrome_user_agent
from cf_clearance_scraper.utils.cookies import format_cookie_header
from cf_clearance_scraper.utils.commands import (
    generate_curl_command,
    generate_wget_command, 
    generate_aria2_command,
)
from cf_clearance_scraper.utils.storage import write_cookie_record

logger = logging.getLogger(__name__)

# Mapeo de tipos de desafío a mensajes
CHALLENGE_MESSAGES = {
    ChallengeType.JAVASCRIPT: "Solving Cloudflare challenge [JavaScript]...",
    ChallengeType.MANAGED: "Solving Cloudflare challenge [Managed]...",
    ChallengeType.INTERACTIVE: "Solving Cloudflare challenge [Interactive]...",
}


def parse_args() -> argparse.Namespace:
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description=(
            "A simple program for scraping Cloudflare clearance (cf_clearance) cookies "
            "from websites issuing Cloudflare challenges to visitors"
        )
    )

    parser.add_argument(
        "url", 
        metavar="URL", 
        help="The URL to scrape the Cloudflare clearance cookie from", 
        type=str
    )

    parser.add_argument(
        "-f", "--file",
        default=None,
        help="The file to write the Cloudflare clearance cookie information to, in JSON format",
        type=str,
    )

    parser.add_argument(
        "-t", "--timeout",
        default=30,
        help="The timeout in seconds to use for solving challenges",
        type=float,
    )

    parser.add_argument(
        "-p", "--proxy",
        default=None,
        help="The proxy server URL to use for the browser requests",
        type=str,
    )

    parser.add_argument(
        "-ua", "--user-agent",
        default=None,
        help="The user agent to use for the browser requests",
        type=str,
    )

    parser.add_argument(
        "--disable-http2", 
        action="store_true",
        help="Disable the usage of HTTP/2 for the browser requests"
    )
    
    parser.add_argument(
        "--disable-http3", 
        action="store_true",
        help="Disable the usage of HTTP/3 for the browser requests"
    )
    
    parser.add_argument(
        "--headed", 
        action="store_true",
        help="Run the browser in headed mode"
    )
    
    parser.add_argument(
        "-ac", "--all-cookies", 
        action="store_true",
        help="Retrieve all cookies from the page, not just the Cloudflare clearance cookie"
    )
    
    parser.add_argument(
        "-c", "--curl", 
        action="store_true",
        help="Get the cURL command for the request with the cookies and user agent"
    )
    
    parser.add_argument(
        "-w", "--wget", 
        action="store_true",
        help="Get the Wget command for the request with the cookies and user agent"
    )
    
    parser.add_argument(
        "-a", "--aria2", 
        action="store_true",
        help="Get the aria2 command for the request with the cookies and user agent"
    )

    return parser.parse_args()


async def navigate_and_collect(
    *,
    solver: CloudflareSolver,
    url: str,
) -> Tuple[List[T_JSON_DICT], Optional[T_JSON_DICT], str]:
    """
    Navega a URL, resuelve desafíos y recolecta cookies.
    
    Parameters
    ----------
    solver : CloudflareSolver
        Instancia del solver.
    url : str
        URL objetivo.
        
    Returns
    -------
    Tuple[List[T_JSON_DICT], Optional[T_JSON_DICT], str]
        (todas_las_cookies, clearance_cookie, user_agent)
    """
    logger.info(f"Navegando a {url}")

    try:
        await solver.navigate_to(url)
    except asyncio.TimeoutError as err:
        logger.error(f"Timeout navegando a {url}: {err}")
        return [], None, ""

    all_cookies = await solver.get_cookies()
    clearance_cookie = solver.extract_clearance_cookie(all_cookies)

    if clearance_cookie is None:
        await solver.set_user_agent_metadata(await solver.get_current_user_agent())
        challenge_platform = await solver.detect_challenge()

        if challenge_platform is None:
            logger.error("No se detectó desafío de Cloudflare.")
            return [], None, ""

        logger.info(CHALLENGE_MESSAGES[challenge_platform])

        try:
            success = await solver.solve_challenge()
            if not success:
                logger.warning("No se pudo resolver el desafío completamente.")
        except asyncio.TimeoutError:
            logger.warning("Timeout resolviendo el desafío.")

        all_cookies = await solver.get_cookies()
        clearance_cookie = solver.extract_clearance_cookie(all_cookies)

    user_agent = await solver.get_current_user_agent()
    return all_cookies, clearance_cookie, user_agent


def setup_logging(debug: bool = False) -> None:
    """Configura el sistema de logging."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )
    
    # Silenciar logs de zendriver a menos que sea debug
    logging.getLogger("zendriver").setLevel(logging.WARNING if not debug else logging.DEBUG)


def display_results(
    *,
    all_cookies: List[T_JSON_DICT],
    clearance_cookie: Optional[T_JSON_DICT],
    user_agent: str,
    args: argparse.Namespace,
) -> None:
    """Muestra los resultados obtenidos."""
    if clearance_cookie is None:
        logger.error("No se pudo obtener cookie de clearance de Cloudflare.")
        return

    cookie_header = format_cookie_header(all_cookies)

    if args.all_cookies:
        logger.info(f"Todas las cookies: {cookie_header}")
    else:
        logger.info(f"Cookie: cf_clearance={clearance_cookie['value']}")

    logger.info(f"User agent: {user_agent}")

    # Generar comandos si se solicitan
    cookies_for_commands = (
        cookie_header if args.all_cookies 
        else f'cf_clearance={clearance_cookie["value"]}'
    )

    if args.curl:
        curl_cmd = generate_curl_command(
            url=args.url,
            cookies_header=cookies_for_commands,
            user_agent=user_agent,
            proxy=args.proxy,
        )
        logger.info(curl_cmd)

    if args.wget:
        if args.proxy is not None:
            logger.warning(
                "Los proxies deben configurarse en variable de entorno o archivo de config para Wget."
            )
        
        wget_cmd = generate_wget_command(
            url=args.url,
            cookies_header=cookies_for_commands,
            user_agent=user_agent,
        )
        logger.info(wget_cmd)

    if args.aria2:
        if args.proxy is not None and args.proxy.casefold().startswith("socks"):
            logger.warning("Los proxies SOCKS no son soportados por aria2.")
        
        aria2_cmd = generate_aria2_command(
            url=args.url,
            cookies_header=cookies_for_commands,
            user_agent=user_agent,
            proxy=args.proxy,
        )
        logger.info(aria2_cmd)


async def run_cli() -> None:
    """Función principal del CLI."""
    args = parse_args()
    
    setup_logging(debug=False)
    logger.info(f"Iniciando navegador {'headed' if args.headed else 'headless'}...")

    # Obtener user agent
    user_agent = args.user_agent or get_chrome_user_agent()

    start_time = time.time()
    
    # Ejecutar scraping
    async with CloudflareSolver(
        user_agent=user_agent,
        timeout=args.timeout,
        http2=not args.disable_http2,
        http3=not args.disable_http3,
        headless=not args.headed,
        proxy=args.proxy,
    ) as solver:
        all_cookies, clearance_cookie, resolved_user_agent = await navigate_and_collect(
            solver=solver, 
            url=args.url
        )

    processing_time = time.time() - start_time
    logger.info(f"Procesamiento completado en {processing_time:.2f} segundos")

    # Mostrar resultados
    display_results(
        all_cookies=all_cookies,
        clearance_cookie=clearance_cookie,
        user_agent=resolved_user_agent,
        args=args,
    )

    # Guardar en archivo si se especifica
    if args.file is not None and clearance_cookie is not None:
        write_cookie_record(
            output_path=args.file,
            clearance_cookie=clearance_cookie,
            all_cookies=all_cookies,
            user_agent=resolved_user_agent,
            proxy=args.proxy,
        ) 