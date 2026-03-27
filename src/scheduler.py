"""
APScheduler-based cron job runner.

This module is the heart of the Docker container: it reads all enabled jobs
from the database, registers each with a CronTrigger, and then blocks forever
until interrupted (Ctrl+C / SIGTERM from Docker).
"""

from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src import db, scraper, screenshot, telegram_sender
from src.config import BOT_TOKEN, LOG_FILE
from src.db import JobType, ConditionType


def _execute_job(job_id: int) -> None:
    """The function called by APScheduler for every cron tick."""
    job = db.get_job(job_id)
    if job is None:
        logger.warning(f"Job {job_id} no longer exists in DB — skipping.")
        return

    if job.job_type == JobType.SCREENSHOT:
        logger.info(f"[{job.name}] 📸 Taking screenshot of {job.url} …")
        try:
            png = screenshot.take_screenshot(job.url, full_page=job.full_page)
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
            text = scraper.extract_text(job.url, job.selector)
            
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


def start() -> None:
    """
    Load all enabled jobs from the DB and start the blocking scheduler.

    This is intended to be the Docker container's PID-1 process:
        CMD ["uv", "run", "python", "main.py", "start"]
    """
    db.init_db()
    
    # Configure logging to file with rotation and retention
    logger.add(
        LOG_FILE,
        rotation="10 MB",
        retention="1 week",
        level="INFO",
        backtrace=True,
        diagnose=True,
    )
    
    jobs = [j for j in db.get_jobs() if j.enabled]

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please configure your .env file.")
        return

    scheduler = BlockingScheduler(timezone="UTC")

    for job in jobs:
        scheduler.add_job(
            _execute_job,
            trigger=CronTrigger.from_crontab(job.cron, timezone="UTC"),
            args=[job.id],
            id=str(job.id),
            name=job.name,
            replace_existing=True,
        )
        logger.info(f"Scheduled [{job.name}] — cron: '{job.cron}'")

    if not jobs:
        logger.warning("No enabled jobs found. Add jobs with:  uv run python main.py add")

    logger.info("🚀 Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped gracefully.")
