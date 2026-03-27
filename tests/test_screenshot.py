import pytest
from unittest.mock import MagicMock, patch
from src import screenshot

@patch("src.screenshot.sync_playwright")
def test_take_screenshot_basic(mock_playwright):
    """Test that take_screenshot calls playwright with correct params."""
    # Setup mocks
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value
    mock_page.screenshot.return_value = b"fake-png-bytes"
    
    url = "https://example.com"
    png = screenshot.take_screenshot(url)
    
    assert png == b"fake-png-bytes"
    mock_browser.new_page.assert_called_once_with(viewport={"width": 1280, "height": 900})
    mock_page.goto.assert_called_once_with(url, wait_until="networkidle", timeout=30_000)
    mock_page.screenshot.assert_called_once_with(type="png", full_page=False)

@patch("src.screenshot.sync_playwright")
def test_take_screenshot_full_page(mock_playwright):
    """Test that full_page=True is passed to playwright (TDD: should fail initially)."""
    # Setup mocks
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value
    
    url = "https://example.com"
    # This will fail initially because take_screenshot doesn't accept full_page yet
    try:
        screenshot.take_screenshot(url, full_page=True)
    except TypeError:
        pytest.fail("take_screenshot should accept full_page argument")
    
    mock_page.screenshot.assert_called_once_with(type="png", full_page=True)
