from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Final, Iterable, List, Optional

import zendriver
from selenium_authenticated_proxy import SeleniumAuthenticatedProxy
from zendriver.cdp.network import T_JSON_DICT, Cookie
from zendriver.core.element import Element

COMMAND: Final[str] = (
    '{name}: {binary} --header "Cookie: {cookies}" --header "User-Agent: {user_agent}" {url}'
)


class ZendriverOptions(list):
    """A class for managing zendriver options."""

    def add_argument(self, arg: str) -> None:
        """
        Add an argument to the list of arguments.

        Parameters
        ----------
        arg : str
            The argument
        """
        self.append(arg)


class ChallengePlatform(Enum):
    """Cloudflare challenge platform types."""

    JAVASCRIPT = "non-interactive"
    MANAGED = "managed"
    INTERACTIVE = "interactive"


class CloudflareSolver:
    """
    A class for solving Cloudflare challenges with undetected-chromedriver.

    Parameters
    ----------
    user_agent : str
        The user agent string to use for the browser requests.
    timeout : float
        The timeout in seconds to use for browser actions and solving challenges.
    http2 : bool
        Enable or disable the usage of HTTP/2 for the browser requests.
    http3 : bool
        Enable or disable the usage of HTTP/3 for the browser requests.
    headless : bool
        Enable or disable headless mode for the browser (not supported on Windows).
    proxy : Optional[str]
        The proxy server URL to use for the browser requests.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float,
        http2: bool,
        http3: bool,
        headless: bool,
        proxy: Optional[str],
    ) -> None:
        options = ZendriverOptions()
        options.add_argument(f"--user-agent={user_agent}")

        if not http2:
            options.add_argument("--disable-http2")

        if not http3:
            options.add_argument("--disable-quic")

        if proxy is not None:
            auth_proxy = SeleniumAuthenticatedProxy(proxy, use_legacy_extension=True)
            auth_proxy.enrich_chrome_options(options)

        config = zendriver.Config(headless=headless, browser_args=options)
        self.driver = zendriver.Browser(config)
        self._timeout = timeout

    async def __aenter__(self) -> CloudflareSolver:
        await self.driver.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.driver.stop()

    @staticmethod
    def _format_cookies(cookies: Iterable[Cookie]) -> List[T_JSON_DICT]:
        """
        Format cookies into a list of JSON cookies.

        Parameters
        ----------
        cookies : Iterable[Cookie]
            List of cookies.

        Returns
        -------
        List[T_JSON_DICT]
            List of JSON cookies.
        """
        return [cookie.to_json() for cookie in cookies]

    @staticmethod
    def extract_clearance_cookie(
        cookies: Iterable[T_JSON_DICT],
    ) -> Optional[T_JSON_DICT]:
        """
        Extract the Cloudflare clearance cookie from a list of cookies.

        Parameters
        ----------
        cookies : Iterable[T_JSON_DICT]
            List of cookies.

        Returns
        -------
        Optional[T_JSON_DICT]
            The Cloudflare clearance cookie. Returns None if the cookie is not found.
        """

        for cookie in cookies:
            if cookie["name"] == "cf_clearance":
                return cookie

        return None

    async def get_cookies(self) -> List[T_JSON_DICT]:
        """
        Get all cookies from the current page.

        Returns
        -------
        List[T_JSON_DICT]
            List of cookies.
        """
        return self._format_cookies(await self.driver.cookies.get_all())

    async def detect_challenge(self) -> Optional[ChallengePlatform]:
        """
        Detect the Cloudflare challenge platform on the current page.

        Returns
        -------
        Optional[ChallengePlatform]
            The Cloudflare challenge platform.
        """
        html = await self.driver.main_tab.get_content()

        for platform in ChallengePlatform:
            if f"cType: '{platform.value}'" in html:
                return platform

        return None

    async def solve_challenge(self) -> None:
        """Solve the Cloudflare challenge on the current page."""
        start_timestamp = datetime.now()

        while (
            self.extract_clearance_cookie(await self.get_cookies()) is None
            and await self.detect_challenge() is not None
            and (datetime.now() - start_timestamp).seconds < self._timeout
        ):
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
                and "display: none;" not in challenge.attrs["style"]
            ):
                await asyncio.sleep(1)

                try:
                    await challenge.get_position()
                except Exception:
                    continue

                await challenge.mouse_click()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A simple program for scraping Cloudflare clearance (cf_clearance) cookies from websites issuing Cloudflare challenges to visitors"
    )

    parser.add_argument(
        "url",
        metavar="URL",
        help="The URL to scrape the Cloudflare clearance cookie from",
        type=str,
    )

    parser.add_argument(
        "-f",
        "--file",
        default=None,
        help="The file to write the Cloudflare clearance cookie information to, in JSON format",
        type=str,
    )

    parser.add_argument(
        "-t",
        "--timeout",
        default=30,
        help="The timeout in seconds to use for solving challenges",
        type=float,
    )

    parser.add_argument(
        "-p",
        "--proxy",
        default=None,
        help="The proxy server URL to use for the browser requests",
        type=str,
    )

    parser.add_argument(
        "-ua",
        "--user-agent",
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        help="The user agent to use for the browser requests",
        type=str,
    )

    parser.add_argument(
        "--disable-http2",
        action="store_true",
        help="Disable the usage of HTTP/2 for the browser requests",
    )

    parser.add_argument(
        "--disable-http3",
        action="store_true",
        help="Disable the usage of HTTP/3 for the browser requests",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser in headed mode",
    )

    parser.add_argument(
        "-ac",
        "--all-cookies",
        action="store_true",
        help="Retrieve all cookies from the page, not just the Cloudflare clearance cookie",
    )

    parser.add_argument(
        "-c",
        "--curl",
        action="store_true",
        help="Get the cURL command for the request with the cookies and user agent",
    )

    parser.add_argument(
        "-w",
        "--wget",
        action="store_true",
        help="Get the Wget command for the request with the cookies and user agent",
    )

    parser.add_argument(
        "-a",
        "--aria2",
        action="store_true",
        help="Get the aria2 command for the request with the cookies and user agent",
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )

    logging.getLogger("zendriver").setLevel(logging.WARNING)
    logging.info("Launching %s browser...", "headed" if args.headed else "headless")

    challenge_messages = {
        ChallengePlatform.JAVASCRIPT: "Solving Cloudflare challenge [JavaScript]...",
        ChallengePlatform.MANAGED: "Solving Cloudflare challenge [Managed]...",
        ChallengePlatform.INTERACTIVE: "Solving Cloudflare challenge [Interactive]...",
    }

    async with CloudflareSolver(
        user_agent=args.user_agent,
        timeout=args.timeout,
        http2=not args.disable_http2,
        http3=not args.disable_http3,
        headless=not args.headed,
        proxy=args.proxy,
    ) as solver:
        logging.info("Going to %s...", args.url)

        try:
            await solver.driver.get(args.url)
        except asyncio.TimeoutError as err:
            logging.error(err)
            return

        all_cookies = await solver.get_cookies()
        clearance_cookie = solver.extract_clearance_cookie(all_cookies)

        if clearance_cookie is None:
            challenge_platform = await solver.detect_challenge()

            if challenge_platform is None:
                logging.error("No Cloudflare challenge detected.")
                return

            logging.info(challenge_messages[challenge_platform])

            try:
                await solver.solve_challenge()
            except asyncio.TimeoutError:
                pass

            all_cookies = await solver.get_cookies()
            clearance_cookie = solver.extract_clearance_cookie(all_cookies)

    if clearance_cookie is None:
        logging.error("Failed to retrieve a Cloudflare clearance cookie.")
        return

    cookie_string = "; ".join(
        f'{cookie["name"]}={cookie["value"]}' for cookie in all_cookies
    )

    if args.all_cookies:
        logging.info("All cookies: %s", cookie_string)
    else:
        logging.info("Cookie: cf_clearance=%s", clearance_cookie["value"])

    logging.info("User agent: %s", args.user_agent)

    if args.curl:
        logging.info(
            COMMAND.format(
                name="cURL",
                binary="curl",
                cookies=(
                    cookie_string
                    if args.all_cookies
                    else f'cf_clearance={clearance_cookie["value"]}'
                ),
                user_agent=args.user_agent,
                url=(
                    f"--proxy {args.proxy} {args.url}"
                    if args.proxy is not None
                    else args.url
                ),
            )
        )

    if args.wget:
        if args.proxy is not None:
            logging.warning(
                "Proxies must be set in an environment variable or config file for Wget."
            )

        logging.info(
            COMMAND.format(
                name="Wget",
                binary="wget",
                cookies=(
                    cookie_string
                    if args.all_cookies
                    else f'cf_clearance={clearance_cookie["value"]}'
                ),
                user_agent=args.user_agent,
                url=args.url,
            )
        )

    if args.aria2:
        if args.proxy is not None and args.proxy.casefold().startswith("socks"):
            logging.warning("SOCKS proxies are not supported by aria2.")

        logging.info(
            COMMAND.format(
                name="aria2",
                binary="aria2c",
                cookies=(
                    cookie_string
                    if args.all_cookies
                    else f'cf_clearance={clearance_cookie["value"]}'
                ),
                user_agent=args.user_agent,
                url=(
                    f"--all-proxy {args.proxy} {args.url}"
                    if args.proxy is not None
                    else args.url
                ),
            )
        )

    if args.file is None:
        return

    logging.info("Writing Cloudflare clearance cookie information to %s...", args.file)

    try:
        with open(args.file, encoding="utf-8") as file:
            json_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        json_data: Dict[str, List[Dict[str, Any]]] = {}

    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    unix_timestamp = clearance_cookie["expires"] - timedelta(days=365).total_seconds()
    timestamp = datetime.fromtimestamp(unix_timestamp, tz=local_timezone).isoformat()

    json_data.setdefault(clearance_cookie["domain"], []).append(
        {
            "unix_timestamp": int(unix_timestamp),
            "timestamp": timestamp,
            "cf_clearance": clearance_cookie["value"],
            "cookies": all_cookies,
            "user_agent": args.user_agent,
            "proxy": args.proxy,
        }
    )

    with open(args.file, "w", encoding="utf-8") as file:
        json.dump(json_data, file, indent=4)


if __name__ == "__main__":
    asyncio.run(main())
