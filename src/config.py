"""
Configuration loader.
Values are read from the environment (populated by .env via python-dotenv).
We use .get() so that commands like `list` and `delete` work without a .env file.
"""

import os
import socket
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
DEFAULT_CHAT_ID: str = os.environ.get("DEFAULT_CHAT_ID", "")
LOG_FILE: Path = Path(__file__).parent.parent / "data" / "stalker.log"

# The short hostname is typically the Docker container ID.
CONTAINER_ID: str = socket.gethostname() or "local"
