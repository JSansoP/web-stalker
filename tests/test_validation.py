import pytest
from src import utils

@pytest.mark.parametrize("cron_string, expected", [
    ("* * * * *", True),
    ("0 9 * * *", True),
    ("0 9 * * 1-5", True),
    ("*/30 * * * *", True),
    ("invalid cron", False),
    ("60 * * * *", False),  # Invalid minute
    ("* * * * * *", False),  # Too many fields for standard crontab
])
def test_validate_cron(cron_string, expected):
    """Test CRON expression validation."""
    assert utils.validate_cron(cron_string) == expected

@pytest.mark.parametrize("url, expected", [
    ("https://google.com", True),
    ("http://localhost:8123", True),
    ("https://example.com/path?query=1", True),
    ("random string", False),
    ("ftp://invalid.com", False),
    ("google.com", False),  # Missing protocol
])
def test_validate_url(url, expected):
    """Test URL validation."""
    assert utils.validate_url(url) == expected
