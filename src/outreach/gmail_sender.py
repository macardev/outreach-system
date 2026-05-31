from __future__ import annotations

import base64
import logging
import random
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.outreach.config import settings
from src.outreach.warmup import can_send_more

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

_gmail_service = None


def setup_gmail_service(credentials_path: str | None = None) -> Any:
    global _gmail_service
    creds_path = credentials_path or settings.GMAIL_CREDENTIALS_PATH
    token_path = settings.GMAIL_TOKEN_PATH

    creds = None
    try:
        import os

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, _SCOPES)
    except Exception as e:
        logger.warning("Could not load token: %s", e)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception:
                logger.info("Browser OAuth failed, trying console mode...")
                try:
                    creds = flow.run_console()
                except Exception as e2:
                    logger.error("OAuth flow failed: %s", e2)
                    raise

        try:
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        except Exception as e:
            logger.warning("Could not save token: %s", e)

    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def send_email(
    to_email: str,
    subject: str,
    body: str,
    business_id: str | None = None,
    email_type: str = "outreach",
) -> dict[str, Any]:
    if not _is_allowed_time():
        logger.info("Outside send hours. Queueing email to %s", to_email)
        return {"message_id": None, "sent_at": None, "status": "queued_time"}

    if not can_send_more():
        logger.info("Daily warmup limit reached. Queueing email to %s", to_email)
        return {"message_id": None, "sent_at": None, "status": "queued_limit"}

    if _is_weekend():
        logger.info("Weekend detected. Queueing email to %s", to_email)
        return {"message_id": None, "sent_at": None, "status": "queued_weekend"}

    try:
        if _gmail_service is None:
            setup_gmail_service()

        html_body = create_html_email(subject, body)

        message = MIMEMultipart("alternative")
        message["To"] = to_email
        message["From"] = settings.SENDER_EMAIL
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        _apply_random_delay()

        try:
            sent = (
                _gmail_service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 429:
                logger.warning("Gmail API rate limit hit. Pausing for 60s.")
                time.sleep(60)
                sent = (
                    _gmail_service.users()
                    .messages()
                    .send(userId="me", body={"raw": raw})
                    .execute()
                )
            else:
                raise

        sent_at = datetime.now().isoformat()
        message_id = sent.get("id", "")

        logger.info(
            "Email sent to %s | Subject: %s | ID: %s", to_email, subject, message_id
        )

        return {
            "message_id": message_id,
            "sent_at": sent_at,
            "status": "sent",
        }

    except HttpError as e:
        if e.resp.status == 403:
            logger.error("Gmail API quota exceeded. Will try tomorrow.")
            return {"message_id": None, "sent_at": None, "status": "quota_exceeded"}
        logger.error("Gmail API error sending to %s: %s", to_email, e)
        return {"message_id": None, "sent_at": None, "status": "error"}
    except Exception as e:
        logger.error("Error sending email to %s: %s", to_email, e)
        return {"message_id": None, "sent_at": None, "status": "error"}


def create_html_email(subject: str, body: str) -> str:
    body_html = body.replace("\n", "<br>")
    unsubscribe_link = f"https://{settings.WEBSITE}/unsubscribe?email={{EMAIL}}"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; font-size: 15px; line-height: 1.6; color: #333; margin: 0; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto;">
    <div style="background: #f9f9f9; padding: 30px; border-radius: 8px;">
      {body_html}
    </div>
    <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center;">
      <p>{settings.COMPANY_NAME} — {settings.WEBSITE}</p>
      <p>
        <a href="{unsubscribe_link}" style="color: #999; text-decoration: underline;">E-postaları iptal et</a>
      </p>
    </div>
  </div>
</body>
</html>"""
    return html


def queue_email(business_id: str, email_data: dict[str, Any]) -> None:
    try:
        from src.outreach import sheets_manager

        sheets_manager.add_to_queue(business_id, email_data)
        logger.info("Email queued for business %s", business_id)
    except Exception as e:
        logger.error("Could not queue email for %s: %s", business_id, e)


def _is_allowed_time() -> bool:
    if settings.ALLOW_WEEKEND_SENDING:
        return True
    now = datetime.now()
    if now.hour not in settings.SEND_HOURS:
        return False
    return True


def _is_weekend() -> bool:
    if settings.ALLOW_WEEKEND_SENDING:
        return False
    return datetime.now().weekday() >= 5


def _apply_random_delay() -> None:
    delay = random.randint(settings.RANDOM_DELAY_MIN, settings.RANDOM_DELAY_MAX)
    logger.debug("Waiting %s seconds before next send", delay)
    time.sleep(delay)
