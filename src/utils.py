import urllib.parse
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

def validate_cron(cron_string: str) -> bool:
    """Validate a standard crontab expression using APScheduler's CronTrigger."""
    try:
        CronTrigger.from_crontab(cron_string)
        return True
    except Exception as exc:
        logger.debug(f"Invalid cron expression '{cron_string}': {exc}")
        return False

def validate_url(url: str) -> bool:
    """Validate a URL has a protocol and a valid structure."""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ("http", "https")
    except Exception as exc:
        logger.debug(f"Invalid URL '{url}': {exc}")
        return False
