"""
APScheduler-based cron job runner.

This module is the heart of the Docker container: it reads all enabled jobs
from the database, registers each with a CronTrigger, and then blocks forever
until interrupted (Ctrl+C / SIGTERM from Docker).
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src import db, scraper, screenshot, telegram_sender
from src.config import BOT_TOKEN, LOG_FILE, CONTAINER_ID
from src.db import JobType, ConditionType
_JOB_CRONS: dict[str, str] = {}


class InterceptHandler(logging.Handler):
    """
    Bridges standard Python logging (used by APScheduler, etc.) to Loguru.
    Filters out non-ERROR logs from external libraries.
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Check if it's a library or our code
        # Libs like apscheduler, playwright, etc. aren't in the 'src' package.
        is_library = not record.name.startswith("src")
        
        # Filter: if it's a library, only log if it's ERROR or higher
        if is_library and record.levelno < logging.ERROR:
            return

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _execute_job(job_id: int) -> None:
    """The function called by APScheduler for every cron tick."""
    job = db.get_job(job_id)
    if job is None:
        logger.warning(f"Job {job_id} no longer exists in DB — skipping.")
        return

    if job.job_type == JobType.SCREENSHOT:
        logger.info(f"[{job.name}] 📸 Taking screenshot of {job.url} …")
        try:
            png = screenshot.take_screenshot(job.url, full_page=job.full_page, zoom=job.zoom, js_script=job.js_script)
            caption = f"📸 {job.name}\n🔗 {job.url}"
            telegram_sender.send_photo(BOT_TOKEN, job.chat_id, png, caption=caption)
            now = datetime.now(timezone.utc).isoformat()
            db.update_last_run(job_id, now)
            logger.info(f"[{job.name}] ✅ Screenshot sent successfully.")
        except Exception as exc:
            logger.error(f"[{job.name}] ❌ Failed: {exc}")
            
    elif job.job_type == JobType.TEXT:
        logger.info(f"[{job.name}] 📝 Extracting text from {job.url} using selector '{job.selector}' …")
        try:
            if not job.selector:
                raise ValueError("Text job is missing a selector.")
            text = scraper.extract_text(job.url, job.selector, timeout=job.timeout, js_script=job.js_script)
            
            # Evaluate condition
            text_lower = text.lower()
            val_lower = job.condition_value.lower() if job.condition_value else ""
            if job.condition_type == ConditionType.CONTAINS and val_lower not in text_lower:
                logger.info(f"[{job.name}] ⏸️  Skipped: Text does not contain '{job.condition_value}'.")
                return
            elif job.condition_type == ConditionType.DOESNT_CONTAIN and val_lower in text_lower:
                logger.info(f"[{job.name}] ⏸️  Skipped: Text contains '{job.condition_value}'.")
                return
                
            message = f"📝 {job.name}\n🔗 {job.url}\n\n📄 Extracted Text:\n{text}"
            telegram_sender.send_message(BOT_TOKEN, job.chat_id, message)
            now = datetime.now(timezone.utc).isoformat()
            db.update_last_run(job_id, now)
            logger.info(f"[{job.name}] ✅ Text sent successfully.")
        except Exception as exc:
            logger.error(f"[{job.name}] ❌ Failed: {exc}")


def _sync_jobs(scheduler: BlockingScheduler) -> None:
    """Periodically sync jobs from the database to the scheduler."""
    current_jobs = {str(j.id): j for j in db.get_jobs() if j.enabled}
    scheduled_jobs = {j.id: j for j in scheduler.get_jobs() if j.id != "sync_jobs"}
    
    # Remove jobs that are disabled or deleted
    for job_id in list(scheduled_jobs.keys()):
        if job_id not in current_jobs:
            scheduler.remove_job(job_id)
            _JOB_CRONS.pop(job_id, None)
            logger.info(f"Removed job [{scheduled_jobs[job_id].name}] — it was disabled or deleted.")
            
    # Add or update jobs
    for job_id, job in current_jobs.items():
        if job_id not in scheduled_jobs:
            # New job
            scheduler.add_job(
                _execute_job,
                trigger=CronTrigger.from_crontab(job.cron, timezone="UTC"),
                args=[job.id],
                id=str(job.id),
                name=job.name,
                replace_existing=True,
            )
            _JOB_CRONS[job_id] = job.cron
            logger.info(f"Scheduled [{job.name}] — cron: '{job.cron}'")
        elif _JOB_CRONS.get(job_id) != job.cron or scheduled_jobs[job_id].name != job.name:
            # Job cron or name changed
            scheduler.add_job(
                _execute_job,
                trigger=CronTrigger.from_crontab(job.cron, timezone="UTC"),
                args=[job.id],
                id=str(job.id),
                name=job.name,
                replace_existing=True,
            )
            _JOB_CRONS[job_id] = job.cron
            logger.info(f"Updated schedule for [{job.name}] — new cron: '{job.cron}'")

def start() -> None:
    """
    Load all enabled jobs from the DB and start the blocking scheduler.

    This is intended to be the Docker container's PID-1 process:
        CMD ["uv", "run", "python", "main.py", "start"]
    """
    # 1. Setup logging immediately so initialization errors are recorded
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[container_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # Push the container ID into every log record
    logger.configure(extra={"container_id": CONTAINER_ID})

    # Configure logging to file with rotation and retention
    logger.add(
        LOG_FILE,
        rotation="10 MB",
        retention="1 week",
        level="INFO",
        format=log_format,
        backtrace=True,
        diagnose=True,
    )

    # Intercept standard logging messages (like APScheduler's)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 2. Main Execution loop wrapped in logger.catch
    with logger.catch(message="Fatal crash in scheduler daemon"):
        db.init_db()
        
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN is not set. Please configure your .env file.")
            return

        scheduler = BlockingScheduler(timezone="UTC")

        # Add the sync job to run every 30 seconds
        scheduler.add_job(
            _sync_jobs,
            "interval",
            seconds=30,
            args=[scheduler],
            id="sync_jobs",
            name="Database Sync"
        )
        
        # Run an initial sync to load jobs immediately
        _sync_jobs(scheduler)

        if not _JOB_CRONS:
            logger.warning("No enabled jobs found. Add jobs with:  uv run python main.py add")

        logger.info("🚀 Scheduler running. Press Ctrl+C to stop.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped gracefully.")
