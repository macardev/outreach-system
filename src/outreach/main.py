from __future__ import annotations

import argparse
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from src.outreach.config import settings

console = Console()

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent.parent


def setup_logging() -> None:
    log_path = PROJECT_DIR / settings.LOG_FILE
    handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


def cmd_setup() -> None:
    console.print("[bold cyan]🚀 Outreach Sistemi — Kurulum Sihirbazı[/bold cyan]")
    console.print()

    env_path = PROJECT_DIR / ".env"

    existing = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    existing[k] = v.replace('"', "")

    console.print(
        "[yellow]Google Cloud Console'da aşağıdaki API'leri aktifleştirin:[/yellow]"
    )
    console.print(
        "  1. Google Maps API → https://console.cloud.google.com/apis/library/places-backend.googleapis.com"
    )
    console.print(
        "  2. Gmail API → https://console.cloud.google.com/apis/library/gmail.googleapis.com"
    )
    console.print(
        "  3. Google Sheets API → https://console.cloud.google.com/apis/library/sheets.googleapis.com"
    )
    console.print()
    console.print("  Gemini API anahtarı → https://aistudio.google.com/app/apikey")
    console.print()
    console.print(
        "[yellow]credentials.json'ı Google Cloud Console > APIs & Services > Credentials'den indirin[/yellow]"
    )
    console.print()

    console.print("[bold]Şimdi .env dosyasını oluşturuyoruz:[/bold]")
    console.print()

    maps_key = console.input(
        f"Google Maps API Key [{existing.get('GOOGLE_MAPS_API_KEY', 'boş')}]: "
    ).strip()
    gemini_key = console.input(
        f"Gemini API Key [{existing.get('GEMINI_API_KEY', 'boş')}]: "
    ).strip()
    sheet_id = console.input(
        f"Google Sheets ID [{existing.get('SPREADSHEET_ID', 'boş')}]: "
    ).strip()
    sender_name = console.input(
        f"İsim [{existing.get('SENDER_NAME', settings.SENDER_NAME)}]: "
    ).strip()
    sender_email = console.input(
        f"Email [{existing.get('SENDER_EMAIL', settings.SENDER_EMAIL)}]: "
    ).strip()

    env_content = f"""# Outreach System — Environment Configuration
# Created: {datetime.now().strftime("%Y-%m-%d %H:%M")}

# Google API Keys
GOOGLE_MAPS_API_KEY="{maps_key or existing.get("GOOGLE_MAPS_API_KEY", "")}"
GEMINI_API_KEY="{gemini_key or existing.get("GEMINI_API_KEY", "")}"

# Google Sheets
SPREADSHEET_ID="{sheet_id or existing.get("SPREADSHEET_ID", "")}"

# Sender Info
SENDER_NAME="{sender_name or existing.get("SENDER_NAME", settings.SENDER_NAME)}"
SENDER_EMAIL="{sender_email or existing.get("SENDER_EMAIL", settings.SENDER_EMAIL)}"

# Email Warmup (auto-set on first run)
WARMUP_START_DATE="{datetime.now().strftime("%Y-%m-%d")}"
"""

    with open(env_path, "w") as f:
        f.write(env_content)

    console.print()
    console.print("[bold green]✅ .env dosyası oluşturuldu![/bold green]")
    console.print()
    console.print(
        "[yellow]🔑 credentials.json dosyasını outreach-system/ klasörüne kopyalayın.[/yellow]"
    )
    console.print()
    console.print("[cyan]Sonraki adımlar:[/cyan]")
    console.print("  1. python main.py --mode warmup-status")
    console.print(
        "  2. python main.py --mode scrape --city Bilecik --type 'diş kliniği' --limit 5"
    )
    console.print("  3. python main.py --mode send")


def cmd_warmup_status() -> None:
    from src.outreach.warmup import get_warmup_status, log_warmup_status

    log_warmup_status()
    ws = get_warmup_status()

    table = Table(title="📊 Email Warmup Status", style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Mode", "Active" if ws["warmup_mode"] else "Full Speed")
    table.add_row("Current Week", f"Week {ws['current_week']} / 4")
    table.add_row("Daily Limit", str(ws["daily_limit"]))
    table.add_row("Sent Today", str(ws["sent_today"]))
    table.add_row("Remaining Today", str(ws["remaining_today"]))
    table.add_row("Progress", f"{ws['warmup_progress_percent']}%")
    table.add_row("Days Since Start", str(ws["days_since_start"]))
    table.add_row("Full Capacity By", ws["estimated_full_capacity_date"])

    console.print(table)

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )
    with progress:
        task = progress.add_task("Warmup Progress", total=100)
        progress.update(task, completed=ws["warmup_progress_percent"])


def cmd_scrape(city: str, business_type: str, limit: int) -> None:
    from src.outreach.scraper import search_businesses, filter_and_rank
    from src.outreach import sheets_manager

    console.print(
        f"[bold cyan]🔍 Scraping: {business_type} in {city} (limit: {limit})[/bold cyan]"
    )

    businesses = search_businesses(city, business_type)
    if not businesses:
        console.print("[yellow]No businesses found.[/yellow]")
        return

    ranked = filter_and_rank(businesses)
    ranked = ranked[:limit] if limit > 0 else ranked

    console.print(
        f"[green]Found {len(businesses)}, filtered to {len(ranked)} high-priority leads[/green]"
    )

    table = Table(title=f"📋 {business_type.title()} - {city}")
    table.add_column("#", style="dim")
    table.add_column("Name")
    table.add_column("Email", style="cyan")
    table.add_column("Website", style="blue")
    table.add_column("Score", style="bold")
    table.add_column("Rating")

    for i, b in enumerate(ranked[:20], 1):
        table.add_row(
            str(i),
            b.get("name", "")[:30],
            (b.get("email") or "—")[:25],
            b.get("website_quality", "none"),
            str(b.get("priority_score", 0)),
            str(b.get("rating", "—")),
        )

    console.print(table)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Saving to Sheets...", total=len(ranked))
        for b in ranked:
            sheets_manager.add_business(b)
            progress.update(task, advance=1)

    console.print(f"[bold green]✅ {len(ranked)} businesses saved![/bold green]")


def cmd_scrape_all() -> None:
    total = 0
    for city in settings.TARGET_CITIES:
        for biz_type in settings.TARGET_BUSINESS_TYPES:
            console.print(f"[cyan]Scraping {biz_type} in {city}...[/cyan]")
            cmd_scrape(city, biz_type, 0)
            total += 1

    console.print(
        f"[bold green]✅ Scraping complete! {total} city-type combinations processed.[/bold green]"
    )


def cmd_send(min_score: int = 60) -> None:
    from src.outreach import gmail_sender, sheets_manager
    from src.outreach.email_generator import generate_email
    from src.outreach.warmup import get_daily_limit, can_send_more

    gmail_sender.setup_gmail_service()

    queued = sheets_manager.get_queued_emails()
    if queued:
        console.print(f"[cyan]📨 Processing {len(queued)} queued emails...[/cyan]")
        for item in queued:
            if not can_send_more():
                console.print("[yellow]Daily limit reached. Stopping.[/yellow]")
                break
            bid = item.get("business_id", "")
            result = gmail_sender.send_email(
                to_email=item.get("email", ""),
                subject=item.get("subject", ""),
                body=item.get("body", ""),
                business_id=bid,
                email_type=item.get("email_type", "outreach"),
            )
            if result["status"] == "sent":
                sheets_manager.remove_from_queue(bid)
                console.print(
                    f"[green]✓ Queued email sent to {item.get('business_name', bid)}[/green]"
                )

    from src.outreach import sheets_manager

    businesses = []
    try:
        import json
        import os

        backup_file = settings.LOCAL_BACKUP_FILE
        backup_path = os.path.join(os.path.dirname(__file__), "..", "..", backup_file)
        if os.path.exists(backup_path):
            with open(backup_path) as f:
                backup = json.load(f)
            businesses = [
                b["data"] for b in backup if b.get("action") == "scrape_result"
            ]
    except Exception:
        pass

    if not businesses:
        try:
            businesses = sheets_manager.get_unsent_businesses()
        except Exception:
            pass

    if not businesses:
        try:
            from src.outreach.scraper import search_businesses, filter_and_rank

            for city in settings.TARGET_CITIES[:2]:
                for biz_type in settings.TARGET_BUSINESS_TYPES[:3]:
                    results = search_businesses(city, biz_type)
                    ranked = filter_and_rank(results)
                    ranked = [
                        b for b in ranked if b.get("priority_score", 0) >= min_score
                    ]
                    businesses.extend(ranked)
        except Exception as e:
            console.print(f"[red]Error fetching businesses: {e}[/red]")

    daily_limit = get_daily_limit()
    sent = 0
    max_to_send = min(daily_limit - sheets_manager.get_today_sent_count(), 20)

    console.print(
        f"[bold cyan]📨 Sending up to {max_to_send} emails (daily limit: {daily_limit})[/bold cyan]"
    )

    for b in businesses[:max_to_send]:
        if not can_send_more():
            console.print("[yellow]Daily limit reached.[/yellow]")
            break
        if not b.get("email"):
            continue

        try:
            email_data = generate_email(b)
            result = gmail_sender.send_email(
                to_email=b["email"],
                subject=email_data["subject"],
                body=email_data["body"],
                business_id=b.get("place_id", ""),
                email_type="outreach",
            )

            if result["status"] == "sent":
                sending_data = {
                    "message_id": result.get("message_id", ""),
                    "business_id": b.get("place_id", ""),
                    "business_name": b.get("name", ""),
                    "subject": email_data["subject"],
                    "email_type": "outreach",
                    "status": "sent",
                    "sent_at": result.get("sent_at", datetime.now().isoformat()),
                }
                sheets_manager.add_sending(sending_data)
                sheets_manager.update_status(b.get("place_id", ""), "Email Gönderildi")
                sent += 1
                console.print(
                    f"[green]✓ Sent ({sent}/{max_to_send}): {b.get('name', '')}[/green]"
                )

            elif result["status"] in ("queued_limit", "queued_time", "quota_exceeded"):
                gmail_sender.queue_email(
                    b.get("place_id", ""),
                    {
                        "business_name": b.get("name", ""),
                        "email": b["email"],
                        "subject": email_data["subject"],
                        "body": email_data["body"],
                        "email_type": "outreach",
                        "priority": b.get("priority_score", 50),
                    },
                )
                console.print(
                    f"[yellow]⟳ Queued: {b.get('name', '')} ({result['status']})[/yellow]"
                )
                if result["status"] in ("quota_exceeded",):
                    break
        except Exception as e:
            console.print(f"[red]✗ Error: {b.get('name', '')}: {e}[/red]")

    console.print(f"[bold green]✅ Sent {sent} emails[/bold green]")
    try:
        sheets_manager.update_dashboard()
    except Exception:
        pass


def cmd_followup() -> None:
    from src.outreach import follow_up

    console.print("[bold cyan]🔁 Checking follow-ups...[/bold cyan]")
    stats = follow_up.check_and_send_followups()

    table = Table(title="📊 Follow-up Results")
    table.add_column("Metric", style="bold")
    table.add_column("Count")
    table.add_row("Follow-up 1 Sent", str(stats["followup_1_sent"]))
    table.add_row("Follow-up 2 Sent", str(stats["followup_2_sent"]))
    table.add_row("Errors", str(stats["errors"]))
    table.add_row("Marked Cold", str(stats["cold_marked"]))

    console.print(table)


def cmd_report() -> None:
    from src.outreach import sheets_manager

    console.print("[bold cyan]📊 Outreach Dashboard[/bold cyan]")

    try:
        service = sheets_manager.setup_sheets_service()
        if service and settings.SPREADSHEET_ID:
            result = (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=settings.SPREADSHEET_ID,
                    range="Dashboard!A:B",
                )
                .execute()
            )
            rows = result.get("values", [])
            if len(rows) > 1:
                table = Table(title="📈 Performance Metrics")
                table.add_column("Metric", style="bold")
                table.add_column("Value")
                for row in rows[1:]:
                    if len(row) >= 2:
                        table.add_row(row[0], row[1])
                console.print(table)
    except Exception as e:
        console.print(f"[yellow]Dashboard not available: {e}[/yellow]")

    from src.outreach.warmup import get_warmup_status

    ws = get_warmup_status()

    console.print()
    table2 = Table(title="🔥 Warmup Status")
    table2.add_column("Metric", style="bold")
    table2.add_column("Value")
    table2.add_row("Current Week", f"Week {ws['current_week']}")
    table2.add_row("Daily Limit", str(ws["daily_limit"]))
    table2.add_row("Sent Today", str(ws["sent_today"]))
    table2.add_row("Remaining", str(ws["remaining_today"]))
    table2.add_row("Full Capacity", ws["estimated_full_capacity_date"])
    console.print(table2)


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="B2B Email Outreach Automation System")
    parser.add_argument(
        "--mode",
        choices=[
            "scrape",
            "scrape-all",
            "send",
            "followup",
            "report",
            "warmup-status",
        ],
        help="Operation mode",
    )
    parser.add_argument("--city", default="", help="City to scrape (for --mode scrape)")
    parser.add_argument("--type", default="", help="Business type (for --mode scrape)")
    parser.add_argument(
        "--limit", type=int, default=0, help="Max results (0 = unlimited)"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=settings.MIN_PRIORITY_SCORE,
        help="Minimum priority score",
    )
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")

    args = parser.parse_args()

    if args.setup:
        cmd_setup()
        return

    if not args.mode:
        parser.print_help()
        console.print(
            "\n[yellow]💡 Run with --setup first if this is your first time.[/yellow]"
        )
        return

    if args.mode == "warmup-status":
        cmd_warmup_status()
    elif args.mode == "scrape":
        if not args.city or not args.type:
            console.print("[red]--city and --type are required for scrape mode[/red]")
            return
        cmd_scrape(args.city, args.type, args.limit)
    elif args.mode == "scrape-all":
        cmd_scrape_all()
    elif args.mode == "send":
        cmd_send(min_score=args.min_score)
    elif args.mode == "followup":
        cmd_followup()
    elif args.mode == "report":
        cmd_report()

    logger.info("Command completed: %s", args.mode)


if __name__ == "__main__":
    main()
