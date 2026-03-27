"""
Screenshot engine using Playwright's sync API.

On a standard dev machine:
    - Uses Playwright's bundled Chromium if PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH is unset.

Inside Docker (Raspberry Pi / ARM):
    - Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium so Playwright uses
      the system-installed binary rather than its own (which isn't built for ARM).
"""

import os

from playwright.sync_api import sync_playwright
from loguru import logger


def take_screenshot(url: str, full_page: bool = False, zoom: int = 100, js_script: str | None = None) -> bytes:
    """
    Navigate to *url* with a headless Chromium browser and return a PNG screenshot
    as raw bytes.

    If full_page is True, captures the entire scrollable area. Otherwise, 
    viewport is set to 1280×900.
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
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30_000)
        
        if js_script:
            try:
                page.evaluate(js_script)
                page.wait_for_timeout(500)
            except Exception as e:
                logger.warning(f"Failed to execute JS script: {e}")
                
        if zoom != 100:
            try:
                page.evaluate(f"document.body.style.zoom = '{zoom}%'")
                page.wait_for_timeout(500)
            except Exception as e:
                logger.warning(f"Failed to apply zoom: {e}")

        png_bytes = page.screenshot(type="png", full_page=full_page)
        browser.close()

    return png_bytes
