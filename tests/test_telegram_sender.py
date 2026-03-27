import pytest
from unittest.mock import patch, MagicMock
from src import telegram_sender
import httpx

@patch("src.telegram_sender.httpx.Client")
def test_send_message_success(mock_client_class):
    """Test successful message sending."""
    mock_client_instance = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client_instance
    
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client_instance.post.return_value = mock_response

    telegram_sender.send_message("fake_token", "123456", "Hello World!")
    
    mock_client_instance.post.assert_called_once()
    args, kwargs = mock_client_instance.post.call_args
    assert args[0] == "https://api.telegram.org/botfake_token/sendMessage"
    assert kwargs["data"] == {
        "chat_id": "123456",
        "text": "Hello World!"
    }


@patch("src.telegram_sender.httpx.Client")
def test_send_photo_success(mock_client_class):
    """Test successful photo sending."""
    mock_client_instance = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client_instance
    
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client_instance.post.return_value = mock_response

    telegram_sender.send_photo("fake_token", "123456", b"fake_image_bytes", caption="Hello Image!")
    
    mock_client_instance.post.assert_called_once()
    args, kwargs = mock_client_instance.post.call_args
    assert args[0] == "https://api.telegram.org/botfake_token/sendPhoto"
    assert kwargs["data"] == {
        "chat_id": "123456",
        "caption": "Hello Image!"
    }
    assert "photo" in kwargs["files"]
    assert kwargs["files"]["photo"][1] == b"fake_image_bytes"


@patch("src.telegram_sender.httpx.Client")
def test_telegram_api_error(mock_client_class):
    """Test API error raises exception."""
    mock_client_instance = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client_instance
    
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    
    # We need to explicitly raise the exception since mock_response is a MagicMock
    def raise_err():
        raise httpx.HTTPStatusError("API Error", request=MagicMock(), response=mock_response)
        
    mock_response.raise_for_status.side_effect = raise_err
    mock_client_instance.post.return_value = mock_response

    with pytest.raises(httpx.HTTPStatusError):
        telegram_sender.send_message("fake_token", "123456", "Fail")
