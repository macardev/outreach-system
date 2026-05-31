from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.outreach.config import settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_sheets_service = None
_local_backup: list[dict[str, Any]] = []


def setup_sheets_service() -> Any:
    global _sheets_service
    if _sheets_service:
        return _sheets_service

    creds = None
    try:
        import os

        token_path = settings.SHEETS_TOKEN_PATH
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, _SCOPES)
    except Exception as e:
        logger.warning("Could not load sheets token: %s", e)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                pass

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.GMAIL_CREDENTIALS_PATH, _SCOPES
        )
        try:
            creds = flow.run_local_server(port=0)
        except Exception:
            logger.info("Browser OAuth failed, trying console mode...")
            try:
                creds = flow.run_console()
            except Exception as e2:
                logger.error("Sheets OAuth failed: %s", e2)
                return None
        with open(settings.SHEETS_TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    _sheets_service = build("sheets", "v4", credentials=creds)
    _ensure_sheets_exist()
    return _sheets_service


def _ensure_sheets_exist() -> None:
    if not settings.SPREADSHEET_ID:
        logger.warning("SPREADSHEET_ID not set")
        return
    try:
        spreadsheet = (
            _sheets_service.spreadsheets()
            .get(spreadsheetId=settings.SPREADSHEET_ID)
            .execute()
        )
        existing = {s["properties"]["title"] for s in spreadsheet.get("sheets", [])}

        required = {
            "İşletmeler": [
                [
                    "ID",
                    "İşletme Adı",
                    "Tip",
                    "Şehir",
                    "Adres",
                    "Telefon",
                    "Email",
                    "Website",
                    "Website Kalitesi",
                    "Priority Score",
                    "Google Maps URL",
                    "Rating",
                    "Yorum Sayısı",
                    "Eklenme Tarihi",
                    "Durum",
                ],
            ],
            "Gönderimler": [
                [
                    "ID",
                    "İşletme ID",
                    "İşletme Adı",
                    "Gönderim Tarihi",
                    "Konu",
                    "Mail Tipi",
                    "Açıldı mı",
                    "Açılma Tarihi",
                    "Cevap Geldi mi",
                    "Cevap Tarihi",
                    "Follow-up 1 Tarihi",
                    "Follow-up 2 Tarihi",
                    "Durum",
                    "Notlar",
                ],
            ],
            "Dashboard": [
                ["Metrik", "Değer"],
            ],
            "Kuyruk": [
                [
                    "ID",
                    "İşletme ID",
                    "İşletme Adı",
                    "Email",
                    "Konu",
                    "İçerik",
                    "Mail Tipi",
                    "Kuyruğa Eklenme",
                    "Öncelik",
                ],
            ],
        }

        for sheet_name, headers in required.items():
            if sheet_name not in existing:
                body = {
                    "requests": [{"addSheet": {"properties": {"title": sheet_name}}}]
                }
                _sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=settings.SPREADSHEET_ID, body=body
                ).execute()
                _sheets_service.spreadsheets().values().update(
                    spreadsheetId=settings.SPREADSHEET_ID,
                    range=f"{sheet_name}!A1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()
                logger.info("Created sheet: %s", sheet_name)
    except Exception as e:
        logger.warning("Could not ensure sheets exist: %s", e)


def add_business(business_data: dict[str, Any]) -> str | None:
    row_id = business_data.get("place_id", "")
    try:
        values = [
            [
                row_id,
                business_data.get("name", ""),
                business_data.get("type", ""),
                business_data.get("city", ""),
                business_data.get("address", ""),
                business_data.get("phone", ""),
                business_data.get("email", ""),
                business_data.get("website", ""),
                business_data.get("website_quality", ""),
                business_data.get("priority_score", 0),
                business_data.get("maps_url", ""),
                business_data.get("rating", ""),
                business_data.get("review_count", 0),
                business_data.get("found_at", datetime.now().isoformat()),
                "Yeni",
            ]
        ]

        service = setup_sheets_service()
        if service and settings.SPREADSHEET_ID:
            service.spreadsheets().values().append(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="İşletmeler!A:O",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
            logger.info("Business added to sheets: %s", business_data.get("name"))
        else:
            _backup_local("add_business", business_data)
            logger.info("Business saved locally: %s", business_data.get("name"))

        return row_id
    except HttpError as e:
        logger.warning("Sheets API error adding business: %s", e)
        _backup_local("add_business", business_data)
        return row_id
    except Exception as e:
        logger.warning("Error adding business: %s", e)
        _backup_local("add_business", business_data)
        return row_id


def update_status(business_id: str, status: str) -> None:
    try:
        row = _find_row_by_id("İşletmeler", business_id)
        if row:
            col = 14
            service = setup_sheets_service()
            if service and settings.SPREADSHEET_ID:
                service.spreadsheets().values().update(
                    spreadsheetId=settings.SPREADSHEET_ID,
                    range=f"İşletmeler!{_col_letter(col)}{row}",
                    valueInputOption="RAW",
                    body={"values": [[status]]},
                ).execute()
    except Exception as e:
        logger.warning("Could not update status: %s", e)


def add_sending(sending_data: dict[str, Any]) -> str | None:
    row_id = sending_data.get("message_id", "")
    try:
        values = [
            [
                row_id,
                sending_data.get("business_id", ""),
                sending_data.get("business_name", ""),
                sending_data.get("sent_at", datetime.now().isoformat()),
                sending_data.get("subject", ""),
                sending_data.get("email_type", "outreach"),
                "Hayır",
                "",
                "Hayır",
                "",
                "",
                "",
                sending_data.get("status", "sent"),
                "",
            ]
        ]

        service = setup_sheets_service()
        if service and settings.SPREADSHEET_ID:
            service.spreadsheets().values().append(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Gönderimler!A:N",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
    except Exception as e:
        logger.warning("Could not add sending record: %s", e)
        _backup_local("add_sending", sending_data)

    return row_id


def update_sending(sending_id: str, field: str, value: str) -> None:
    field_map = {
        "opened": (6, "Açıldı mı"),
        "opened_date": (7, "Açılma Tarihi"),
        "replied": (8, "Cevap Geldi mi"),
        "reply_date": (9, "Cevap Tarihi"),
        "followup_1": (10, "Follow-up 1 Tarihi"),
        "followup_2": (11, "Follow-up 2 Tarihi"),
        "status": (12, "Durum"),
        "notes": (13, "Notlar"),
    }
    if field not in field_map:
        return
    col = field_map[field][0]
    try:
        row = _find_row_by_id("Gönderimler", sending_id, col_offset=0)
        if row:
            service = setup_sheets_service()
            if service and settings.SPREADSHEET_ID:
                service.spreadsheets().values().update(
                    spreadsheetId=settings.SPREADSHEET_ID,
                    range=f"Gönderimler!{_col_letter(col)}{row}",
                    valueInputOption="RAW",
                    body={"values": [[value]]},
                ).execute()
    except Exception as e:
        logger.warning("Could not update sending: %s", e)


def get_pending_followups() -> list[dict[str, Any]]:
    pendings = []
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return pendings

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Gönderimler!A:N",
            )
            .execute()
        )
        rows = result.get("values", [])
        if len(rows) <= 1:
            return pendings

        for row in rows[1:]:
            if len(row) < 14:
                continue
            replied = row[8] if len(row) > 8 else "Hayır"
            followup_1 = row[10] if len(row) > 10 else ""
            followup_2 = row[11] if len(row) > 11 else ""
            sent_at_str = row[3] if len(row) > 3 else ""

            if replied.lower() == "evet":
                continue

            business_id = row[1] if len(row) > 1 else ""
            business_name = row[2] if len(row) > 2 else ""
            subject = row[4] if len(row) > 4 else ""

            if not sent_at_str:
                continue

            try:
                sent_at = datetime.fromisoformat(sent_at_str)
            except ValueError:
                continue

            now = datetime.now()

            if not followup_1 and (now - sent_at).days >= settings.FOLLOWUP_1_DELAY:
                pendings.append(
                    {
                        "sending_row": row,
                        "business_id": business_id,
                        "business_name": business_name,
                        "followup_number": 1,
                        "original_subject": subject,
                    }
                )

            if followup_1 and not followup_2:
                try:
                    f1_date = datetime.fromisoformat(followup_1)
                except ValueError:
                    continue
                if (now - f1_date).days >= settings.FOLLOWUP_2_DELAY:
                    pendings.append(
                        {
                            "sending_row": row,
                            "business_id": business_id,
                            "business_name": business_name,
                            "followup_number": 2,
                            "original_subject": subject,
                        }
                    )

        return pendings
    except Exception as e:
        logger.warning("Could not get pending followups: %s", e)
        return pendings


def get_queued_emails() -> list[dict[str, Any]]:
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return _load_local_queue()

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Kuyruk!A:I",
            )
            .execute()
        )
        rows = result.get("values", [])
        if len(rows) <= 1:
            return []

        queued = []
        for row in rows[1:]:
            if len(row) >= 4:
                queued.append(
                    {
                        "business_id": row[1],
                        "business_name": row[2] if len(row) > 2 else "",
                        "email": row[3] if len(row) > 3 else "",
                        "subject": row[4] if len(row) > 4 else "",
                        "body": row[5] if len(row) > 5 else "",
                        "email_type": row[6] if len(row) > 6 else "outreach",
                        "added_at": row[7] if len(row) > 7 else "",
                    }
                )
        return queued
    except Exception as e:
        logger.warning("Could not get queued emails: %s", e)
        return _load_local_queue()


def add_to_queue(business_id: str, email_data: dict[str, Any]) -> None:
    try:
        import uuid

        row_id = str(uuid.uuid4())[:8]
        values = [
            [
                row_id,
                business_id,
                email_data.get("business_name", ""),
                email_data.get("email", ""),
                email_data.get("subject", ""),
                email_data.get("body", ""),
                email_data.get("email_type", "outreach"),
                datetime.now().isoformat(),
                email_data.get("priority", 50),
            ]
        ]

        service = setup_sheets_service()
        if service and settings.SPREADSHEET_ID:
            service.spreadsheets().values().append(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Kuyruk!A:I",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
            logger.info("Added to queue: %s", business_id)
        else:
            _backup_local("queue", {"business_id": business_id, **email_data})
    except Exception as e:
        logger.warning("Could not add to queue: %s", e)
        _backup_local("queue", {"business_id": business_id, **email_data})


def remove_from_queue(business_id: str) -> None:
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Kuyruk!A:I",
            )
            .execute()
        )
        rows = result.get("values", [])
        if len(rows) <= 1:
            return

        for i, row in enumerate(rows[1:], start=2):
            if len(row) > 1 and row[1] == business_id:
                service.spreadsheets().values().update(
                    spreadsheetId=settings.SPREADSHEET_ID,
                    range=f"Kuyruk!A{i}",
                    valueInputOption="RAW",
                    body={"values": [["", "", "", "", "", "", "", "", ""]]},
                ).execute()
                break
    except Exception as e:
        logger.warning("Could not remove from queue: %s", e)


def get_all_contacted_place_ids() -> list[str]:
    ids = []
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return ids

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="İşletmeler!A:O",
            )
            .execute()
        )
        rows = result.get("values", [])
        for row in rows[1:]:
            if row and row[0]:
                ids.append(row[0])
        return ids
    except Exception as e:
        logger.warning("Could not get contacted place IDs: %s", e)
        return ids


def get_today_sent_count() -> int:
    today_str = date.today().isoformat()
    count = 0
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return count

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Gönderimler!D:D",
            )
            .execute()
        )
        rows = result.get("values", [])
        for row in rows[1:]:
            if row and row[0].startswith(today_str):
                count += 1
        return count
    except Exception as e:
        logger.warning("Could not get today's sent count: %s", e)
        return count


def update_dashboard() -> None:
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="İşletmeler!A:O",
            )
            .execute()
        )
        businesses = result.get("values", [])[1:]

        result2 = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="Gönderimler!A:N",
            )
            .execute()
        )
        sendings = result2.get("values", [])[1:]

        total_scanned = len(businesses)
        email_sent_count = len(sendings)
        opened_count = sum(1 for r in sendings if len(r) > 6 and r[6].lower() == "evet")
        replied_count = sum(
            1 for r in sendings if len(r) > 8 and r[8].lower() == "evet"
        )
        converted_count = sum(
            1 for r in businesses if len(r) > 14 and r[14].lower() == "müşteri"
        )

        open_rate = (
            round((opened_count / email_sent_count * 100), 1) if email_sent_count else 0
        )
        reply_rate = (
            round((replied_count / email_sent_count * 100), 1)
            if email_sent_count
            else 0
        )
        conversion_rate = (
            round((converted_count / email_sent_count * 100), 1)
            if email_sent_count
            else 0
        )

        from src.outreach.warmup import get_warmup_status

        ws = get_warmup_status()

        today_sent = get_today_sent_count()

        metrics = [
            ["Toplam Taranan İşletme", str(total_scanned)],
            ["Email Gönderilen İşletme", str(email_sent_count)],
            ["Mail Açılma Oranı (%)", str(open_rate)],
            ["Cevap Oranı (%)", str(reply_rate)],
            ["Müşteriye Dönüşüm Oranı (%)", str(conversion_rate)],
            ["Bu Hafta Gönderilen", str(email_sent_count)],
            ["Bugün Gönderilen / Günlük Limit", f"{today_sent} / {ws['daily_limit']}"],
            ["Mevcut Hafta (Isındırma)", f"Hafta {ws['current_week']}"],
            ["Tahmini Tam Kapasite Tarihi", ws["estimated_full_capacity_date"]],
            ["Pipeline Değeri (TL)", "0"],
            ["Toplam Kazanılan (TL)", "0"],
        ]

        service.spreadsheets().values().update(
            spreadsheetId=settings.SPREADSHEET_ID,
            range="Dashboard!A2:B",
            valueInputOption="RAW",
            body={"values": metrics},
        ).execute()
        logger.info("Dashboard updated")
    except Exception as e:
        logger.warning("Could not update dashboard: %s", e)


def mark_as_client(business_id: str, deal_value_tl: float) -> None:
    try:
        update_status(business_id, "Müşteri")
        row = _find_row_by_id("İşletmeler", business_id)
        if row:
            service = setup_sheets_service()
            if service and settings.SPREADSHEET_ID:
                pass
        logger.info(
            "Business %s marked as client. Value: %.2f TL", business_id, deal_value_tl
        )
    except Exception as e:
        logger.warning("Could not mark as client: %s", e)


def get_business_email(business_id: str) -> str | None:
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return None
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="İşletmeler!A:O",
            )
            .execute()
        )
        rows = result.get("values", [])
        for row in rows[1:]:
            if len(row) > 0 and row[0] == business_id and len(row) > 6:
                return row[6]
        return None
    except Exception:
        return None


def get_business_by_id(business_id: str) -> dict[str, Any] | None:
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return None
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="İşletmeler!A:O",
            )
            .execute()
        )
        rows = result.get("values", [])
        headers = [
            "place_id",
            "name",
            "type",
            "city",
            "address",
            "phone",
            "email",
            "website",
            "website_quality",
            "priority_score",
            "maps_url",
            "rating",
            "review_count",
            "found_at",
            "status",
        ]
        for row in rows[1:]:
            if len(row) > 0 and row[0] == business_id:
                return dict(zip(headers, row))
        return None
    except Exception:
        return None


def _find_row_by_id(sheet: str, row_id: str, col_offset: int = 0) -> int | None:
    try:
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return None
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range=f"{sheet}!A:Z",
            )
            .execute()
        )
        rows = result.get("values", [])
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > col_offset and row[col_offset] == row_id:
                return i
        return None
    except Exception:
        return None


def _col_letter(col: int) -> str:
    return chr(65 + col)


def _backup_local(action: str, data: dict[str, Any]) -> None:
    try:
        backup = _load_local_backup()
        backup.append(
            {
                "action": action,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )
        with open(settings.LOCAL_BACKUP_FILE, "w") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Could not write local backup: %s", e)


def _load_local_backup() -> list[dict[str, Any]]:
    try:
        import os

        if os.path.exists(settings.LOCAL_BACKUP_FILE):
            with open(settings.LOCAL_BACKUP_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _load_local_queue() -> list[dict[str, Any]]:
    backup = _load_local_backup()
    return [b["data"] for b in backup if b.get("action") == "queue"]


def get_unsent_businesses(min_score: int = 60) -> list[dict[str, Any]]:
    """Get businesses from İşletmeler sheet that haven't been contacted yet."""
    try:
        sent_ids = set(get_all_contacted_place_ids())
        service = setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return []

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.SPREADSHEET_ID,
                range="İşletmeler!A:O",
            )
            .execute()
        )
        rows = result.get("values", [])
        if len(rows) <= 1:
            return []

        headers = ["place_id", "name", "type", "city", "address", "phone", "email",
                    "website", "website_quality", "priority_score", "maps_url",
                    "rating", "review_count", "found_at", "status"]

        unsent = []
        for row in rows[1:]:
            if len(row) < 15:
                continue
            pid = row[0]
            if pid in sent_ids:
                continue
            email = row[6].strip() if len(row) > 6 and row[6] else ""
            if not email or "@" not in email:
                continue
            try:
                rating = float(row[11].replace(",", ".")) if row[11] else 0
            except ValueError:
                rating = 0
            try:
                reviews = int(row[12]) if row[12] else 0
            except ValueError:
                reviews = 0
            try:
                score = int(row[9]) if row[9] else 0
            except ValueError:
                score = 0

            business = dict(zip(headers, row[:15]))
            business["rating"] = rating
            business["review_count"] = reviews
            business["priority_score"] = score
            business["email"] = email
            unsent.append(business)

        unsent.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        logger.info(f"Found {len(unsent)} unsent businesses with emails from Sheet")
        return unsent
    except Exception as e:
        logger.warning(f"Could not get unsent businesses: {e}")
        return []


def sync_local_backup() -> None:
    backup = _load_local_backup()
    if not backup:
        return
    logger.info("Syncing %d local backup records to Sheets...", len(backup))
    for record in backup:
        action = record.get("action")
        data = record.get("data", {})
        try:
            if action == "add_business":
                add_business(data)
            elif action == "add_sending":
                add_sending(data)
        except Exception:
            pass
    try:
        import os

        os.remove(settings.LOCAL_BACKUP_FILE)
        logger.info("Local backup synced and cleared")
    except Exception:
        pass
