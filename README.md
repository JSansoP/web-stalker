# web-stalker 📸

Cron-based web screenshot notifier. Visits URLs on a schedule, takes screenshots with Playwright, and sends them to a Telegram chat.

**Designed for:** Raspberry Pi + Docker deployment.

---

## Setup

### 1. Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- A Telegram Bot token (create one via [@BotFather](https://t.me/BotFather))
- Your Telegram chat ID

### 2. Install dependencies

```sh
uv sync
uv run playwright install chromium   # only needed for local dev; Docker uses system chromium
```

### 3. Configure

```sh
cp .env.example .env
# Edit .env and fill in BOT_TOKEN and DEFAULT_CHAT_ID
```

---

## CLI Usage

```sh
# Add a job (with optional full-page screenshot)
uv run python main.py add --name "Google" --url "https://google.com" --cron "0 9 * * *" --full-page

# Update a job
uv run python main.py update 1 --url "https://newsite.com" --cron "*/30 * * * *" --full-page

# Enable / Disable a job
uv run python main.py disable 1
uv run python main.py enable 1

# Show job details
uv run python main.py show 1

# List all jobs
uv run python main.py list

# View scheduler logs
uv run python main.py logs --lines 50

# Run a job immediately (great for testing)
uv run python main.py run 1

# Delete a job
uv run python main.py delete 1

# Start the scheduler daemon (blocking)
uv run python main.py start
```

---

## Docker (Raspberry Pi)

```sh
# Build and start the daemon
docker compose up -d

# Watch logs
docker compose logs -f

# Add a job from the host
docker compose exec web-stalker uv run python main.py add \
  --name "Home Assistant" \
  --url "http://homeassistant.local:8123" \
  --cron "0 * * * *"
```

The SQLite database (`data/jobs.db`) is stored in a bind-mounted volume (`./data/`) and persists across container restarts and rebuilds.

---

## Project Structure

```
web-stalker/
├── main.py                  # Entrypoint
├── src/
│   ├── cli.py               # Typer CLI commands
│   ├── scheduler.py         # APScheduler daemon (Docker PID-1)
│   ├── screenshot.py        # Playwright screenshot engine
│   ├── telegram_sender.py   # Telegram Bot API sender
│   ├── db.py                # SQLite job store
│   └── config.py            # .env loader
├── data/                    # SQLite DB (gitignored)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Cron Expression Examples

| Expression      | Meaning                  |
|-----------------|--------------------------|
| `* * * * *`     | Every minute             |
| `0 9 * * *`     | Every day at 09:00 UTC   |
| `0 9 * * 1-5`   | Weekdays at 09:00 UTC    |
| `*/30 * * * *`  | Every 30 minutes         |
