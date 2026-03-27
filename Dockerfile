# ─────────────────────────────────────────────────────────────────────────────
# web-stalker Dockerfile
#
# Targets Raspberry Pi (ARM64) by installing the system Chromium via apt
# instead of Playwright's bundled binary (which isn't built for ARM).
#
# The PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH env var tells the Python code
# to use /usr/bin/chromium transparently.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.13-slim

# ── System deps ──────────────────────────────────────────────────────────────
# chromium: the browser used for screenshots
# libgl1, fonts-liberation: common rendering deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        fonts-liberation \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ── Playwright config ─────────────────────────────────────────────────────────
# Point Playwright's Python API to the system-installed Chromium.
# This skips the need for `playwright install` and works on ARM64.
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

# ── uv ───────────────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Project ───────────────────────────────────────────────────────────────────
WORKDIR /app

# Install dependencies first (layer is cached unless pyproject.toml changes)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

# Copy source
COPY . .

# Create the data directory (will normally be overridden by a bind mount)
RUN mkdir -p data

# ── Default command: run the blocking scheduler daemon ────────────────────────
CMD ["uv", "run", "python", "main.py", "start"]
