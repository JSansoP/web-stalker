import pytest
from unittest.mock import MagicMock, patch
from src import scraper

@patch("src.scraper.sync_playwright")
def test_extract_text_success(mock_playwright):
    """Test that extract_text calls playwright correctly and returns text."""
    # Setup mocks
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value
    
    mock_element = MagicMock()
    mock_element.inner_text.return_value = "  Extracted Text!  "
    mock_page.wait_for_selector.return_value = mock_element
    
    url = "https://example.com"
    selector = "h1"
    
    result = scraper.extract_text(url, selector)
    
    assert result == "Extracted Text!"
    mock_page.goto.assert_called_once_with(url, wait_until="networkidle", timeout=30_000)
    mock_page.wait_for_selector.assert_called_once_with(selector, state="attached", timeout=10_000)

@patch("src.scraper.sync_playwright")
def test_extract_text_not_found(mock_playwright):
    """Test that extract_text raises a ValueError if the selector is missing."""
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value
    
    # Return None for the selector to simulate not found
    mock_page.wait_for_selector.return_value = None
    
    url = "https://example.com"
    selector = ".missing-div"
    
    with pytest.raises(ValueError, match="Selector '.missing-div' not found"):
        scraper.extract_text(url, selector)
