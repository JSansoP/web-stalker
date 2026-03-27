import pytest
from typer.testing import CliRunner
from src.cli import app
from src import db

runner = CliRunner()

def test_cli_add_invalid_url(mock_db):
    """Test that adding a job with an invalid URL fails."""
    result = runner.invoke(app, ["add", "--name", "Test", "--url", "invalid-url", "--cron", "* * * * *"])
    assert result.exit_code != 0
    assert "Invalid URL" in result.output

def test_cli_add_invalid_cron(mock_db):
    """Test that adding a job with an invalid CRON fails."""
    result = runner.invoke(app, ["add", "--name", "Test", "--url", "https://example.com", "--cron", "invalid cron"])
    assert result.exit_code != 0
    assert "Invalid CRON expression" in result.output

def test_cli_update_job(mock_db, sample_job_data):
    """Test the update command (TDD: should fail initially)."""
    job_id = db.add_job(**sample_job_data)
    
    # Update URL and Name
    result = runner.invoke(app, ["update", str(job_id), "--name", "New Name", "--url", "https://new.com"])
    assert result.exit_code == 0
    assert "updated" in result.output
    
    job = db.get_job(job_id)
    assert job.name == "New Name"
    assert job.url == "https://new.com"

def test_cli_toggle_job(mock_db, sample_job_data):
    """Test enable/disable/toggle command (TDD: should fail initially)."""
    job_id = db.add_job(**sample_job_data)
    
    # Disable
    result = runner.invoke(app, ["disable", str(job_id)])
    assert result.exit_code == 0
    assert "disabled" in result.output
    assert db.get_job(job_id).enabled is False
    
    # Enable
    result = runner.invoke(app, ["enable", str(job_id)])
    assert result.exit_code == 0
    assert "enabled" in result.output
    assert db.get_job(job_id).enabled is True

def test_cli_show_job(mock_db, sample_job_data):
    """Test the show command (TDD: should fail initially)."""
    job_id = db.add_job(**sample_job_data)
    
    result = runner.invoke(app, ["show", str(job_id)])
    assert result.exit_code == 0
    assert sample_job_data["name"] in result.output
    assert sample_job_data["url"] in result.output

def test_cli_add_full_page(mock_db):
    """Test adding a job with the --full-page flag."""
    result = runner.invoke(app, ["add", "--name", "Full", "--url", "https://example.com", "--cron", "* * * * *", "--full-page"])
    assert result.exit_code == 0
    assert "Job added" in result.output
    
    assert db.get_jobs()[0].full_page is True

def test_cli_update_full_page(mock_db, sample_job_data):
    """Test updating the full_page flag via CLI."""
    job_id = db.add_job(**sample_job_data)
    
    # Enable full-page
    result = runner.invoke(app, ["update", str(job_id), "--full-page"])
    assert result.exit_code == 0
    assert db.get_job(job_id).full_page is True
    
    # Disable full-page
    result = runner.invoke(app, ["update", str(job_id), "--no-full-page"])
    assert result.exit_code == 0
    assert db.get_job(job_id).full_page is False

def test_cli_help_alias(mock_db):
    """Test that -h works as a help alias."""
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0
    assert "📸 Cron-based web screenshot notifier" in result.output

def test_cli_add_text_job(mock_db):
    """Test adding a text job requires a selector."""
    # Fails without selector
    result_fail = runner.invoke(app, ["add", "--name", "Text", "--url", "https://ex.com", "--cron", "* * * * *", "--type", "text"])
    assert result_fail.exit_code != 0
    assert "is required" in result_fail.output
    
    # Succeeds with selector
    result_success = runner.invoke(app, ["add", "--name", "Text", "--url", "https://ex.com", "--cron", "* * * * *", "--type", "text", "--selector", "h1"])
    assert result_success.exit_code == 0
    assert "type='text'" in result_success.output
    
    jobs = db.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].job_type.value == "text"
    assert jobs[0].selector == "h1"

def test_cli_update_to_text(mock_db, sample_job_data):
    """Test updating a job to text requires a selector."""
    job_id = db.add_job(**sample_job_data)
    
    # Fails without selector
    result_fail = runner.invoke(app, ["update", str(job_id), "--type", "text"])
    assert result_fail.exit_code != 0
    assert "is required" in result_fail.output
    
    # Succeeds with selector
    result_success = runner.invoke(app, ["update", str(job_id), "--type", "text", "--selector", ".class"])
    assert result_success.exit_code == 0
    
    job = db.get_job(job_id)
    assert job.job_type.value == "text"
    assert job.selector == ".class"

def test_cli_add_text_job_contains(mock_db):
    """Test adding a text job with conditions."""
    # Fails with both
    result_both = runner.invoke(app, ["add", "--name", "Text", "--url", "https://ex.com", "--cron", "* * * * *", "--type", "text", "--selector", "h1", "--contains", "foo", "--not-contains", "bar"])
    assert result_both.exit_code != 0
    assert "Cannot use both" in result_both.output

    # Fails with condition on screenshot type
    result_screenshot = runner.invoke(app, ["add", "--name", "Text", "--url", "https://ex.com", "--cron", "* * * * *", "--contains", "foo"])
    assert result_screenshot.exit_code != 0
    assert "only valid for 'text' jobs" in result_screenshot.output

    # Succeeds
    result_success = runner.invoke(app, ["add", "--name", "Text", "--url", "https://ex.com", "--cron", "* * * * *", "--type", "text", "--selector", "h1", "--contains", "Sale"])
    assert result_success.exit_code == 0
    
    jobs = db.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].condition_type.value == "contains"
    assert jobs[0].condition_value == "Sale"
