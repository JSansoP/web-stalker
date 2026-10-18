"""
Optional heartbeat pings to heartbeat-monitor.

A scheduler tick job calls send() every few minutes to prove the daemon is
alive. Sending must never break or slow down the scheduler: short timeout,
every error is caught and only logged, and nothing is sent when HEARTBEAT_URL
is unset.
"""

import urllib.request

from loguru import logger

from src import config

TIMEOUT = 5


def send(suffix: str = "") -> bool:
    """GET HEARTBEAT_URL, or HEARTBEAT_URL/<suffix>. Returns True on HTTP 200."""
    if not config.HEARTBEAT_URL:
        return False
    url = config.HEARTBEAT_URL.rstrip("/") + (f"/{suffix}" if suffix else "")
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return response.status == 200
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Heartbeat {suffix or 'success'} failed: {exc}")
        return False
