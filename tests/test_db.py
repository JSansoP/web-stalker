import sqlite3
from src import db
from src.db import JobType, ConditionType

def test_init_db(mock_db):
    """Test that init_db creates the jobs table and schema correctly."""
    # Already initialized by the fixture
    with sqlite3.connect(mock_db) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cur.fetchone() is not None

def test_add_get_job(mock_db, sample_job_data):
    """Test adding and retrieving a job."""
    job_id = db.add_job(**sample_job_data)
    assert job_id > 0
    
    job = db.get_job(job_id)
    assert job is not None
    assert job.id == job_id
    assert job.name == sample_job_data["name"]
    assert job.url == sample_job_data["url"]
    assert job.cron == sample_job_data["cron"]
    assert job.chat_id == sample_job_data["chat_id"]
    assert job.enabled is True
    assert job.last_run is None
    assert job.full_page is False
    assert job.job_type == JobType.SCREENSHOT
    assert job.selector is None
    assert job.condition_type is None
    assert job.condition_value is None

def test_add_get_text_job(mock_db):
    """Test adding and retrieving a text extraction job."""
    job_id = db.add_job(
        name="Text Job", 
        url="https://example.com", 
        cron="* * * * *", 
        chat_id="123", 
        job_type=JobType.TEXT, 
        selector="h1",
        condition_type=ConditionType.CONTAINS,
        condition_value="Sale"
    )
    
    job = db.get_job(job_id)
    assert job.job_type == JobType.TEXT
    assert job.selector == "h1"
    assert job.condition_type == ConditionType.CONTAINS
    assert job.condition_value == "Sale"

def test_get_jobs(mock_db, sample_job_data):
    """Test getting all jobs."""
    db.add_job(**sample_job_data)
    db.add_job(name="Second Job", url="https://goog.le", cron="* * * * *", chat_id="987")
    
    jobs = db.get_jobs()
    assert len(jobs) == 2

def test_delete_job(mock_db, sample_job_data):
    """Test deleting a job."""
    job_id = db.add_job(**sample_job_data)
    assert db.delete_job(job_id) is True
    assert db.get_job(job_id) is None
    assert db.delete_job(999) is False

def test_update_last_run(mock_db, sample_job_data):
    """Test updating the last_run timestamp."""
    job_id = db.add_job(**sample_job_data)
    now_iso = "2024-03-27T16:00:00Z"
    db.update_last_run(job_id, now_iso)
    
    job = db.get_job(job_id)
    assert job.last_run == now_iso

def test_update_job(mock_db, sample_job_data):
    """Test updating job details."""
    job_id = db.add_job(**sample_job_data)
    
    # Update only some fields
    db.update_job(job_id, name="New Name", url="https://new.url")
    job = db.get_job(job_id)
    assert job.name == "New Name"
    assert job.url == "https://new.url"
    assert job.cron == sample_job_data["cron"]  # Unchanged
    
    # Update all fields
    db.update_job(job_id, name="Final", url="https://final.url", cron="0 0 * * *", chat_id="999")
    job = db.get_job(job_id)
    assert job.name == "Final"
    assert job.url == "https://final.url"
    assert job.cron == "0 0 * * *"
    assert job.chat_id == "999"
    
    # Update full_page and type
    db.update_job(job_id, full_page=True, job_type=JobType.TEXT, selector=".main")
    assert db.get_job(job_id).full_page is True
    assert db.get_job(job_id).job_type == JobType.TEXT
    assert db.get_job(job_id).selector == ".main"
    db.update_job(job_id, full_page=False)
    assert db.get_job(job_id).full_page is False

def test_toggle_job(mock_db, sample_job_data):
    """Test enabling/disabling a job."""
    job_id = db.add_job(**sample_job_data)
    
    # Disable
    db.toggle_job(job_id, enabled=False)
    job = db.get_job(job_id)
    assert job.enabled is False
    
    # Enable
    db.toggle_job(job_id, enabled=True)
    job = db.get_job(job_id)
    assert job.enabled is True
