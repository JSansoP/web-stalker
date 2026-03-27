"""
Telegram Bot API — photo sender.

Uses httpx (sync) to POST to the sendPhoto endpoint.
Raises httpx.HTTPStatusError on any non-2xx response.
"""

import httpx
from loguru import logger


def send_photo(
    bot_token: str,
    chat_id: str,
    photo_bytes: bytes,
    caption: str = "",
) -> None:
    """
    Send *photo_bytes* (PNG) to a Telegram chat.

    Args:
        bot_token:   The Telegram Bot API token (from @BotFather).
        chat_id:     Target chat / channel / group ID.
        photo_bytes: Raw PNG bytes to send as a photo.
        caption:     Optional caption shown below the photo (max 1024 chars).
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    with httpx.Client(timeout=30) as client:
        response = client.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": ("screenshot.png", photo_bytes, "image/png")},
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(f"Telegram API error ({exc.response.status_code}): {exc.response.text}")
        raise

def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
) -> None:
    """
    Send a plain text message to a Telegram chat.

    Args:
        bot_token: The Telegram Bot API token (from @BotFather).
        chat_id:   Target chat / channel / group ID.
        text:      The text message to send.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    with httpx.Client(timeout=30) as client:
        response = client.post(
            url,
            data={"chat_id": chat_id, "text": text},
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(f"Telegram API error ({exc.response.status_code}): {exc.response.text}")
        raise
