from __future__ import annotations

import logging
from datetime import date, datetime

from src.outreach import sheets_manager
from src.outreach.config import settings

logger = logging.getLogger(__name__)


def get_current_week() -> int:
    start_str = _get_or_set_start_date()
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    today = date.today()
    days_since_start = (today - start).days
    if days_since_start < 0:
        return 1
    week = (days_since_start // 7) + 1
    return max(1, min(week, 4))


def get_daily_limit() -> int:
    if not settings.WARMUP_MODE:
        return settings.MAX_EMAILS_PER_DAY
    week = get_current_week()
    schedule = {int(k): v for k, v in settings.WARMUP_SCHEDULE.items()}
    return schedule.get(week, settings.MAX_EMAILS_PER_DAY)


def get_emails_sent_today() -> int:
    try:
        count = sheets_manager.get_today_sent_count()
        return count
    except Exception:
        logger.warning("Could not get today's sent count from Sheets", exc_info=True)
        return 0


def can_send_more() -> bool:
    sent = get_emails_sent_today()
    limit = get_daily_limit()
    return sent < limit


def get_warmup_status() -> dict:
    start_str = _get_or_set_start_date()
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    today = date.today()
    days_since = (today - start).days
    week = get_current_week()
    daily_limit = get_daily_limit()
    sent_today = get_emails_sent_today()
    remaining = max(0, daily_limit - sent_today)
    progress_pct = min(100, int((week / 4) * 100))
    estimated_full = _calc_full_capacity_date(start)

    return {
        "current_week": week,
        "daily_limit": daily_limit,
        "sent_today": sent_today,
        "remaining_today": remaining,
        "warmup_progress_percent": progress_pct,
        "days_since_start": max(0, days_since),
        "estimated_full_capacity_date": estimated_full,
        "warmup_mode": settings.WARMUP_MODE,
    }


def _get_or_set_start_date() -> str:
    if settings.WARMUP_START_DATE:
        return settings.WARMUP_START_DATE
    today_str = date.today().strftime("%Y-%m-%d")
    try:
        import os

        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                content = f.read()
            if "WARMUP_START_DATE=" not in content:
                with open(env_path, "a") as f:
                    f.write(f'\nWARMUP_START_DATE="{today_str}"\n')
    except Exception:
        pass
    return today_str


def _calc_full_capacity_date(start_date: date) -> str:
    from datetime import timedelta

    full_date = start_date + timedelta(weeks=4)
    return full_date.strftime("%Y-%m-%d")


def log_warmup_status() -> None:
    status = get_warmup_status()
    logger.info(
        "Warmup Status | Week: %s | Limit: %s/day | Sent Today: %s | "
        "Progress: %s%% | Full Capacity: %s",
        status["current_week"],
        status["daily_limit"],
        status["sent_today"],
        status["warmup_progress_percent"],
        status["estimated_full_capacity_date"],
    )
