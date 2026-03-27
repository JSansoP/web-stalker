import os
import sqlite3
import pytest
from pathlib import Path
from src import db

@pytest.fixture
def mock_db(tmp_path, request):
    """Fixture to set up a unique temporary SQLite database for each test."""
    test_db_path = tmp_path / f"test_jobs_{request.node.name}.db"
    
    # Monkeypatch the DB_PATH in src.db
    original_db_path = db.DB_PATH
    db.DB_PATH = test_db_path
    
    # Initialize the database
    db.init_db()
    
    yield test_db_path
    
    # Restore the original DB_PATH
    db.DB_PATH = original_db_path
    
    # Force close any remaining connections if possible (not easy with monkeypatching)
    # But using unique paths should prevent the immediate collision.

@pytest.fixture
def sample_job_data():
    """Fixture for constant sample job data."""
    return {
        "name": "Test Job",
        "url": "https://example.com",
        "cron": "* * * * *",
        "chat_id": "123456789"
    }
