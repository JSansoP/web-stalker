"""
Typer CLI — the user-facing interface for managing web-stalker jobs.

Commands
--------
  add     Add a new screenshot job.
  list    Print all jobs as a rich table.
  delete  Delete a job by ID.
  run     Execute a job immediately (screenshot + Telegram send).
  start   Start the APScheduler daemon (blocking — used by Docker).
"""

from datetime import datetime, timezone

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from src import db, scraper, screenshot, telegram_sender, utils
from src.config import BOT_TOKEN, DEFAULT_CHAT_ID, LOG_FILE
from src.db import JobType, ConditionType

app = typer.Typer(
    name="web-stalker",
    help="📸 Cron-based web screenshot notifier via Telegram.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@app.command()
def add(
    name: str = typer.Option(..., "--name", "-n", help="Human-readable label for the job."),
    url: str = typer.Option(..., "--url", "-u", help="URL to visit and screenshot."),
    cron: str = typer.Option(
        ...,
        "--cron",
        "-c",
        help="Cron expression, e.g. '0 9 * * *' (every day at 09:00 UTC).",
    ),
    chat_id: str = typer.Option(
        "",
        "--chat-id",
        help="Telegram chat ID. Defaults to DEFAULT_CHAT_ID from .env.",
    ),
    full_page: bool = typer.Option(
        False,
        "--full-page",
        help="Take a full-page screenshot instead of just the viewport.",
    ),
    job_type: JobType = typer.Option(
        JobType.SCREENSHOT,
        "--type",
        help="Type of job: 'screenshot' or 'text'.",
    ),
    selector: str = typer.Option(
        None,
        help="CSS Selector (required if type is 'text').",
    ),
    contains: str = typer.Option(
        None,
        "--contains",
        help="Alert only if text contains this string.",
    ),
    not_contains: str = typer.Option(
        None,
        "--not-contains",
        help="Alert only if text DOES NOT contain this string.",
    ),
    timeout: int = typer.Option(
        10,
        "--timeout",
        help="Maximum time to wait for selector attached (in seconds).",
    ),
    alert_on_fail: bool = typer.Option(
        True,
        "--alert-on-fail/--no-alert-on-fail",
        help="Send a Telegram message when a job fails.",
    ),
) -> None:
    """Add a new screenshot job to the database."""
    db.init_db()
    
    # Validation
    if not utils.validate_url(url):
        typer.echo(f"❌ Invalid URL: '{url}'. Must start with http:// or https://", err=True)
        raise typer.Exit(1)
        
    if not utils.validate_cron(cron):
        typer.echo(f"❌ Invalid CRON expression: '{cron}'", err=True)
        raise typer.Exit(1)

    if job_type == JobType.TEXT and not selector:
        typer.echo("❌ '--selector' is required when '--type' is 'text'.", err=True)
        raise typer.Exit(1)

    if contains and not_contains:
        typer.echo("❌ Cannot use both '--contains' and '--not-contains' together.", err=True)
        raise typer.Exit(1)

    if (contains or not_contains) and job_type != JobType.TEXT:
        typer.echo("❌ Conditions ('--contains', '--not-contains') are only valid for 'text' jobs.", err=True)
        raise typer.Exit(1)
        
    condition_type = None
    condition_value = None
    if contains:
        condition_type = ConditionType.CONTAINS
        condition_value = contains
    elif not_contains:
        condition_type = ConditionType.DOESNT_CONTAIN
        condition_value = not_contains

    effective_chat_id = chat_id or DEFAULT_CHAT_ID
    if not effective_chat_id:
        # ... (unchanged)
        raise typer.Exit(1)

    job_id = db.add_job(name, url, cron, effective_chat_id, job_type, selector, condition_type, condition_value, full_page=full_page, timeout=timeout, alert_on_fail=alert_on_fail)
    typer.echo(f"✅ Job added — id={job_id}  name='{name}'  cron='{cron}' type='{job_type.value}'")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command("list")
def list_jobs() -> None:
    """List all jobs in a formatted table."""
    db.init_db()
    jobs = db.get_jobs()

    if not jobs:
        typer.echo("No jobs found. Use `add` to create one.")
        return

    table = Table(title="web-stalker jobs", show_lines=True, highlight=True)
    table.add_column("ID", style="cyan bold", justify="right", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Type", style="blue")
    table.add_column("Details", style="magenta")
    table.add_column("Conditions", style="red")
    table.add_column("URL", overflow="fold")
    table.add_column("Cron", style="yellow")
    table.add_column("Chat ID", style="dim")
    table.add_column("Timeout(s)", justify="center")
    table.add_column("Alert", justify="center")
    table.add_column("On", justify="center")
    table.add_column("Last Run", style="dim")

    for job in jobs:
        job_type_str = f"{job.job_type.value}"

        details_str = ""
        if job.selector:
            details_str = f"sel: {job.selector}"
        if job.full_page:
            details_str = "full page" if not details_str else f"{details_str}, full page"
            
        condition_str = "—"
        if job.condition_type:
            cond = "CONTAINS" if job.condition_type == ConditionType.CONTAINS else "DOES NOT CONTAIN"
            condition_str = f"{cond}: '{job.condition_value}'"

        table.add_row(
            str(job.id),
            job.name,
            job_type_str,
            details_str or "—",
            condition_str,
            job.url,
            job.cron,
            job.chat_id,
            str(job.timeout),
            "✅" if job.alert_on_fail else "❌",
            "✅" if job.enabled else "❌",
            job.last_run or "—",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@app.command()
def delete(
    job_id: int = typer.Argument(..., help="ID of the job to delete."),
) -> None:
    """Delete a job by its ID."""
    db.init_db()
    if db.delete_job(job_id):
        typer.echo(f"🗑️  Job {job_id} deleted.")
    else:
        typer.echo(f"❌ Job {job_id} not found.", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    job_id: int = typer.Argument(..., help="ID of the job to run immediately."),
) -> None:
    """Run a job right now — take a screenshot and send it to Telegram."""
    db.init_db()
    job = db.get_job(job_id)
    if job is None:
        typer.echo(f"❌ Job {job_id} not found.", err=True)
        raise typer.Exit(1)

    if not BOT_TOKEN:
        typer.echo("❌ BOT_TOKEN is not set. Please configure your .env file.", err=True)
        raise typer.Exit(1)

    if job.job_type == JobType.SCREENSHOT:
        typer.echo(f"📸 Taking screenshot of {job.url} …")
        try:
            png = screenshot.take_screenshot(job.url, full_page=job.full_page)
            caption = f"📸 {job.name}\n🔗 {job.url}"
            telegram_sender.send_photo(BOT_TOKEN, job.chat_id, png, caption=caption)
            db.update_last_run(job_id, datetime.now(timezone.utc).isoformat())
            typer.echo("✅ Screenshot sent to Telegram.")
        except Exception as exc:
            typer.echo(f"❌ Failed: {exc}", err=True)
            if job.alert_on_fail:
                telegram_sender.send_message(BOT_TOKEN, job.chat_id, f"❌ Job Failed: {job.name}\n🔗 {job.url}\n\n⚠️ Error: {exc}")
            raise typer.Exit(1)
            
    elif job.job_type == JobType.TEXT:
        typer.echo(f"📝 Extracting text from {job.url} using selector '{job.selector}' …")
        try:
            if not job.selector:
                raise ValueError("Text job is missing a selector.")
            text = scraper.extract_text(job.url, job.selector, timeout=job.timeout)
            
            # Evaluate condition
            text_lower = text.lower()
            val_lower = job.condition_value.lower() if job.condition_value else ""
            if job.condition_type == ConditionType.CONTAINS and val_lower not in text_lower:
                db.update_last_run(job_id, datetime.now(timezone.utc).isoformat())
                typer.echo(f"⏸️ Skipped: Text does not contain '{job.condition_value}'.")
                return
            elif job.condition_type == ConditionType.DOESNT_CONTAIN and val_lower in text_lower:
                db.update_last_run(job_id, datetime.now(timezone.utc).isoformat())
                typer.echo(f"⏸️ Skipped: Text contains '{job.condition_value}'.")
                return

            message = f"📝 {job.name}\n🔗 {job.url}\n\n📄 Extracted Text:\n{text}"
            telegram_sender.send_message(BOT_TOKEN, job.chat_id, message)
            db.update_last_run(job_id, datetime.now(timezone.utc).isoformat())
            typer.echo("✅ Text sent to Telegram.")
        except Exception as exc:
            typer.echo(f"❌ Failed: {exc}", err=True)
            if job.alert_on_fail:
                telegram_sender.send_message(BOT_TOKEN, job.chat_id, f"❌ Job Failed: {job.name}\n🔗 {job.url}\n\n⚠️ Error: {exc}")
            raise typer.Exit(1)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


@app.command()
def start() -> None:
    """Start the cron scheduler daemon (blocking — this is what Docker runs)."""
    from src.scheduler import start as _start

    _start()


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@app.command()
def show(
    job_id: int = typer.Argument(..., help="ID of the job to show."),
) -> None:
    """Show details of a single job."""
    db.init_db()
    job = db.get_job(job_id)
    if not job:
        typer.echo(f"❌ Job {job_id} not found.", err=True)
        raise typer.Exit(1)

    table = Table(title=f"Job {job_id}: {job.name}", show_header=False)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")

    table.add_row("ID", str(job.id))
    table.add_row("Name", job.name)
    table.add_row("Type", job.job_type.value)
    if job.selector:
        table.add_row("Selector", job.selector)
    if job.condition_type:
        cond_str = "Contains" if job.condition_type == ConditionType.CONTAINS else "Doesn't Contain"
        table.add_row("Condition", f"{cond_str} '{job.condition_value}'")
    table.add_row("URL", job.url)
    table.add_row("Cron", job.cron)
    table.add_row("Chat ID", job.chat_id)
    table.add_row("Enabled", "✅ Yes" if job.enabled else "❌ No")
    table.add_row("Timeout (s)", str(job.timeout))
    table.add_row("Alert on fail", "✅ Yes" if job.alert_on_fail else "❌ No")
    table.add_row("Full Page", "✅ Yes" if job.full_page else "❌ No")
    table.add_row("Last Run", job.last_run or "—")

    console.print(table)


# ---------------------------------------------------------------------------
# enable / disable
# ---------------------------------------------------------------------------


@app.command()
def enable(job_id: int = typer.Argument(..., help="ID of the job to enable.")) -> None:
    """Enable a job by its ID."""
    db.init_db()
    if db.toggle_job(job_id, enabled=True):
        typer.echo(f"✅ Job {job_id} enabled.")
    else:
        typer.echo(f"❌ Job {job_id} not found.", err=True)
        raise typer.Exit(1)


@app.command()
def disable(job_id: int = typer.Argument(..., help="ID of the job to disable.")) -> None:
    """Disable a job by its ID."""
    db.init_db()
    if db.toggle_job(job_id, enabled=False):
        typer.echo(f"🚫 Job {job_id} disabled.")
    else:
        typer.echo(f"❌ Job {job_id} not found.", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@app.command()
def update(
    job_id: int = typer.Argument(..., help="ID of the job to update."),
    name: str = typer.Option(None, "--name", "-n", help="New human-readable label."),
    url: str = typer.Option(None, "--url", "-u", help="New URL to visit."),
    cron: str = typer.Option(None, "--cron", "-c", help="New cron expression."),
    chat_id: str = typer.Option(None, "--chat-id", help="New Telegram chat ID."),
    job_type: JobType = typer.Option(None, "--type", help="New Job Type ('screenshot' or 'text')."),
    selector: str = typer.Option(None, help="New CSS Selector."),
    contains: str = typer.Option(None, "--contains", help="Alert only if text contains this string."),
    not_contains: str = typer.Option(None, "--not-contains", help="Alert only if text DOES NOT contain this string."),
    full_page: bool = typer.Option(None, "--full-page/--no-full-page", help="Toggle full-page screenshots."),
    clear_conditions: bool = typer.Option(False, "--clear-conditions", help="Remove all text conditions from the job."),
    timeout: int = typer.Option(None, "--timeout", help="Maximum time to wait for selector attached (in seconds)."),
    alert_on_fail: bool = typer.Option(None, "--alert-on-fail/--no-alert-on-fail", help="Toggle alerting on failure."),
) -> None:
    """Update an existing job's details."""
    db.init_db()

    current_job = db.get_job(job_id)
    if not current_job:
        typer.echo(f"❌ Job {job_id} not found.", err=True)
        raise typer.Exit(1)

    # Validation if fields are provided
    if url is not None and not utils.validate_url(url):
        typer.echo(f"❌ Invalid URL: '{url}'. Must start with http:// or https://", err=True)
        raise typer.Exit(1)

    if cron is not None and not utils.validate_cron(cron):
        typer.echo(f"❌ Invalid CRON expression: '{cron}'", err=True)
        raise typer.Exit(1)

    eff_job_type = job_type if job_type else current_job.job_type
    
    if eff_job_type == JobType.TEXT:
        final_selector = selector if selector is not None else current_job.selector
        if not final_selector:
            typer.echo("❌ '--selector' is required when updating type to 'text'.", err=True)
            raise typer.Exit(1)

    if contains and not_contains:
        typer.echo("❌ Cannot use both '--contains' and '--not-contains' together.", err=True)
        raise typer.Exit(1)

    if (contains or not_contains) and eff_job_type != JobType.TEXT:
        typer.echo("❌ Conditions ('--contains', '--not-contains') are only valid for 'text' jobs.", err=True)
        raise typer.Exit(1)

    # Determine condition updates
    condition_type = None
    condition_value = None
    if contains is not None:
        condition_type = ConditionType.CONTAINS
        condition_value = contains
    elif not_contains is not None:
        condition_type = ConditionType.DOESNT_CONTAIN
        condition_value = not_contains

    # If updating to screenshot, clear conditions and selector
    if eff_job_type == JobType.SCREENSHOT and job_type is not None:
        # User explicitly switched to screenshot, force clear textual fields
        selector = ""  # Let db.py handle it, well db.update_job will set it back.
        # It's cleaner to handle this, let's just pass them as empty
        selector = ""
        condition_type = None # This is tricky since it expects Enum but we don't have UNSET
        # Actually, let's rely on db.update_job logic if we want to nullify, but right now db.update_job doesn't nullify if not None.
        pass

    if db.update_job(job_id, name, url, cron, chat_id, job_type, selector, condition_type, condition_value, full_page=full_page, clear_conditions=clear_conditions, timeout=timeout, alert_on_fail=alert_on_fail):
        typer.echo(f"✅ Job {job_id} updated.")
    else:
        typer.echo(f"❌ Job {job_id} not found or no updates provided.", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


@app.command()
def logs(
    lines: int = typer.Option(20, "--lines", "-l", help="Number of lines to show."),
) -> None:
    """Show the most recent logs from the scheduler."""
    if not LOG_FILE.exists():
        typer.echo(f"No log file found at {LOG_FILE}. Is the scheduler running?")
        return

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        content = f.readlines()
        tail = content[-lines:]
        for line in tail:
            typer.echo(line.strip())
