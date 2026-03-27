"""
Scraping engine using Playwright's sync API.

Extracts text content from a DOM element matched by a CSS selector.
"""

import os

from playwright.sync_api import sync_playwright
from loguru import logger


def extract_text(url: str, selector: str, timeout: int = 10, js_script: str | None = None) -> str:
    """
    Navigate to *url* with a headless Chromium browser, wait for the *selector*,
    and return its innerText. Raises an exception if the selector is not found.
    """
    executable_path: str | None = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=executable_path,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",  # important inside Docker
            ],
        )
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        
        if js_script:
            try:
                page.evaluate(js_script)
                page.wait_for_timeout(500)
            except Exception as e:
                logger.warning(f"Failed to execute JS script: {e}")
        
        # Wait for the selector to be attached to the DOM
        element = page.wait_for_selector(selector, state="attached", timeout=timeout * 1000)
        
        if not element:
            browser.close()
            raise ValueError(f"Selector '{selector}' not found on {url}")
            
        text = element.inner_text()
        browser.close()

    return text.strip()
