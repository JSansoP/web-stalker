from unittest.mock import patch, MagicMock
import pytest
from apscheduler.schedulers.blocking import BlockingScheduler

from src import scheduler, db
from src.db import JobType, ConditionType


@patch("src.scheduler.telegram_sender")
@patch("src.scheduler.screenshot")
def test_execute_job_screenshot(mock_screenshot, mock_telegram, mock_db, sample_job_data):
    """Test executing a screenshot job."""
    # Add a job to DB first
    job_id = db.add_job(**sample_job_data)
    
    mock_screenshot.take_screenshot.return_value = b"fake_png_data"
    
    # Execute
    scheduler._execute_job(job_id)
    
    # Verify screenshot was taken
    mock_screenshot.take_screenshot.assert_called_once_with(sample_job_data["url"], full_page=False, zoom=100, js_script=None)
    
    # Verify telegram was sent
    mock_telegram.send_photo.assert_called_once()
    assert b"fake_png_data" in mock_telegram.send_photo.call_args[0] or b"fake_png_data" in mock_telegram.send_photo.call_args.kwargs.values()
    
    # Verify last_run was updated
    job = db.get_job(job_id)
    assert job.last_run is not None


@patch("src.scheduler.telegram_sender")
@patch("src.scheduler.scraper")
def test_execute_job_text_no_condition(mock_scraper, mock_telegram, mock_db):
    """Test executing a text job without conditions."""
    job_id = db.add_job(
        name="TextJob",
        url="https://test.com",
        cron="* * * * *",
        chat_id="123",
        job_type=JobType.TEXT,
        selector="h1"
    )
    
    mock_scraper.extract_text.return_value = "Hello World"
    
    scheduler._execute_job(job_id)
    
    mock_scraper.extract_text.assert_called_once_with("https://test.com", "h1", timeout=10, js_script=None)
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert "Hello World" in args[2] if len(args) > 2 else kwargs.get("text", "") or "Hello World" in args[2]
    
    job = db.get_job(job_id)
    assert job.last_run is not None


@patch("src.scheduler.telegram_sender")
@patch("src.scheduler.scraper")
def test_execute_job_text_conditions(mock_scraper, mock_telegram, mock_db):
    """Test executing a text job with conditions."""
    job_id = db.add_job(
        name="TextJob",
        url="https://test.com",
        cron="* * * * *",
        chat_id="123",
        job_type=JobType.TEXT,
        selector="h1",
        condition_type=ConditionType.CONTAINS,
        condition_value="Sale"
    )
    
    # Condition doesn't match
    mock_scraper.extract_text.return_value = "No discount here"
    scheduler._execute_job(job_id)
    mock_telegram.send_message.assert_not_called()
    job = db.get_job(job_id)
    assert job.last_run is None
    
    # Condition matches
    mock_scraper.extract_text.return_value = "Big Summer Sale"
    scheduler._execute_job(job_id)
    mock_telegram.send_message.assert_called_once()
    job = db.get_job(job_id)
    assert job.last_run is not None


def test_sync_jobs_new_job(mock_db, sample_job_data):
    """Test adding a completely new job dynamically via _sync_jobs."""
    db.add_job(**sample_job_data)
    
    # Fresh scheduler, empty global crons state
    scheduler._JOB_CRONS.clear()
    
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = []
    
    scheduler._sync_jobs(mock_scheduler)
    
    mock_scheduler.add_job.assert_called_once()
    assert len(scheduler._JOB_CRONS) == 1


def test_sync_jobs_remove_disabled_job(mock_db, sample_job_data):
    """Test removing a disabled job via _sync_jobs."""
    job_id = db.add_job(**sample_job_data)
    
    scheduler._JOB_CRONS[str(job_id)] = sample_job_data["cron"]
    
    mock_job = MagicMock()
    mock_job.id = str(job_id)
    mock_job.name = sample_job_data["name"]
    
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [mock_job]
    
    # Now disable the job in DB
    db.toggle_job(job_id, enabled=False)
    
    scheduler._sync_jobs(mock_scheduler)
    
    # Verify job removed from scheduler and track dict
    mock_scheduler.remove_job.assert_called_once_with(str(job_id))
    assert str(job_id) not in scheduler._JOB_CRONS


def test_sync_jobs_update_cron(mock_db, sample_job_data):
    """Test dynamically modifying an existing job's cron in the scheduler."""
    job_id = db.add_job(**sample_job_data)
    
    scheduler._JOB_CRONS[str(job_id)] = sample_job_data["cron"]
    
    mock_job = MagicMock()
    mock_job.id = str(job_id)
    mock_job.name = sample_job_data["name"]
    
    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs.return_value = [mock_job]
    
    # Modify the cron in DB
    new_cron = "*/5 * * * *"
    db.update_job(job_id, cron=new_cron)
    
    scheduler._sync_jobs(mock_scheduler)
    
    # Verify job was replaced via add_job with replace_existing=True
    mock_scheduler.add_job.assert_called_once()
    
    args, kwargs = mock_scheduler.add_job.call_args
    assert kwargs.get("replace_existing") is True
    assert kwargs.get("id") == str(job_id)
    assert scheduler._JOB_CRONS[str(job_id)] == new_cron
