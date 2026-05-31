from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.outreach import email_generator, gmail_sender, sheets_manager
from src.outreach.config import settings

logger = logging.getLogger(__name__)


def check_and_send_followups() -> dict[str, int]:
    stats = {"followup_1_sent": 0, "followup_2_sent": 0, "errors": 0, "cold_marked": 0}

    try:
        pendings = sheets_manager.get_pending_followups()
        logger.info("Found %d pending follow-ups", len(pendings))
    except Exception as e:
        logger.error("Could not get pending follow-ups: %s", e)
        return stats

    for pending in pendings:
        try:
            business_id = pending.get("business_id", "")
            followup_number = pending.get("followup_number", 1)
            business_name = pending.get("business_name", "")

            business_data = sheets_manager.get_business_by_id(business_id)
            if not business_data:
                logger.warning("Business data not found for %s", business_id)
                continue

            to_email = business_data.get("email", "")
            if not to_email:
                logger.warning("No email for business %s", business_id)
                sheets_manager.update_sending(business_id, "status", "No Email")
                continue

            followup = email_generator.generate_followup_email(
                business_data, followup_number
            )
            subject = followup.get("subject", "")
            body = followup.get("body", "")

            result = gmail_sender.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                business_id=business_id,
                email_type=f"followup_{followup_number}",
            )

            if result.get("status") == "sent":
                if followup_number == 1:
                    sheets_manager.update_sending(
                        business_id, "followup_1", datetime.now().isoformat()
                    )
                    stats["followup_1_sent"] += 1
                else:
                    sheets_manager.update_sending(
                        business_id, "followup_2", datetime.now().isoformat()
                    )
                    stats["followup_2_sent"] += 1

                sending_data = {
                    "message_id": result.get("message_id", ""),
                    "business_id": business_id,
                    "business_name": business_name,
                    "subject": subject,
                    "email_type": f"followup_{followup_number}",
                    "status": "sent",
                    "sent_at": result.get("sent_at", datetime.now().isoformat()),
                }
                sheets_manager.add_sending(sending_data)
                logger.info("Follow-up %s sent to %s", followup_number, business_name)

            elif result.get("status") in (
                "queued_limit",
                "queued_time",
                "quota_exceeded",
            ):
                logger.info(
                    "Follow-up %s for %s queued: %s",
                    followup_number,
                    business_name,
                    result["status"],
                )
                break
            else:
                stats["errors"] += 1
                sheets_manager.update_sending(
                    business_id,
                    "notlar",
                    f"Follow-up {followup_number} failed: {result['status']}",
                )

        except Exception as e:
            logger.error(
                "Error sending follow-up to %s: %s", pending.get("business_name", ""), e
            )
            stats["errors"] += 1

    try:
        cold_marked = _check_cold_businesses()
        stats["cold_marked"] = cold_marked
    except Exception as e:
        logger.error("Error marking cold businesses: %s", e)

    logger.info("Follow-up run complete: %s", stats)
    return stats


def mark_cold(business_id: str) -> None:
    try:
        sheets_manager.update_status(business_id, "Soğuk")
        sheets_manager.update_sending(business_id, "status", "Soğuk")
        logger.info("Business %s marked as cold", business_id)
    except Exception as e:
        logger.warning("Could not mark business %s as cold: %s", business_id, e)


def schedule_reactivation(business_id: str, days: int = 30) -> None:
    try:
        sheets_manager.update_status(business_id, f"Yeniden {days} gün")
        sheets_manager.update_sending(
            business_id, "notlar", f"Reactivation scheduled in {days} days"
        )
        logger.info(
            "Business %s scheduled for reactivation in %d days", business_id, days
        )
    except Exception as e:
        logger.warning("Could not schedule reactivation for %s: %s", business_id, e)


def check_reactivations() -> list[dict[str, Any]]:

    reactivations = []
    try:
        service = sheets_manager.setup_sheets_service()
        if not service or not settings.SPREADSHEET_ID:
            return reactivations

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
            if len(row) > 14:
                status = row[14]
                if status.startswith("Yeniden"):
                    try:
                        days_str = status.split()[1]
                        days = int(days_str)
                        if days <= 0:
                            reactivations.append(
                                {
                                    "business_id": row[0],
                                    "name": row[1],
                                    "email": row[6] if len(row) > 6 else "",
                                }
                            )
                    except ValueError, IndexError:
                        pass
        return reactivations
    except Exception as e:
        logger.warning("Could not check reactivations: %s", e)
        return reactivations


def _check_cold_businesses() -> int:
    cold_count = 0
    try:
        pendings = sheets_manager.get_pending_followups()
        from datetime import datetime

        now = datetime.now()
        for pending in pendings:
            row = pending.get("sending_row", [])
            if len(row) > 3:
                sent_at_str = row[3]
                followup_2 = row[11] if len(row) > 11 else ""
                try:
                    sent_at = datetime.fromisoformat(sent_at_str)
                    last_action = (
                        datetime.fromisoformat(followup_2) if followup_2 else sent_at
                    )
                    if (now - last_action).days >= settings.COLD_AFTER_DAYS:
                        mark_cold(pending["business_id"])
                        schedule_reactivation(
                            pending["business_id"], settings.REACTIVATE_AFTER_DAYS
                        )
                        cold_count += 1
                except ValueError:
                    continue
        return cold_count
    except Exception as e:
        logger.error("Error checking cold businesses: %s", e)
        return cold_count
