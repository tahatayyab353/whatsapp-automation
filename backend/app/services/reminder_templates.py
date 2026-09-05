from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional


def format_localized_datetime(
    dt_utc: datetime,
    tz_name: str = "Asia/Karachi",
) -> tuple[str, str]:
    """
    Converts a UTC datetime to local clinic timezone and returns formatted (date_str, time_str).
    e.g. ("Monday, Sep 10, 2026", "03:00 PM")
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc)

    local_tz = timezone.utc
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        # Fallback for systems without IANA tzdata (e.g. standard Windows Python installs)
        if tz_name in ("Asia/Karachi", "PKT", "UTC+5"):
            local_tz = timezone(timedelta(hours=5))
        else:
            try:
                local_tz = ZoneInfo("UTC")
            except Exception:
                local_tz = timezone.utc

    local_dt = dt_utc.astimezone(local_tz)
    date_str = local_dt.strftime("%A, %b %d, %Y")
    time_str = local_dt.strftime("%I:%M %p")
    return date_str, time_str



def build_reminder_message(
    reminder_type: str,
    clinic_name: str,
    scheduled_at: datetime,
    tz_name: str = "Asia/Karachi",
    patient_name: Optional[str] = None,
    appointment_title: Optional[str] = None,
) -> str:
    """
    Renders a concise, clinic-appropriate WhatsApp notification message.
    """
    date_str, time_str = format_localized_datetime(scheduled_at, tz_name)
    greeting = f"Hello {patient_name}!" if patient_name else "Hello!"
    title_suffix = f" for *{appointment_title}*" if appointment_title else ""

    if reminder_type == "APPOINTMENT_24H":
        return (
            f"{greeting}\n\n"
            f"This is a friendly reminder that your appointment{title_suffix} at *{clinic_name}* "
            f"is scheduled for tomorrow, *{date_str}* at *{time_str}*.\n\n"
            f"Please reply directly to this message if you need to reschedule or ask any questions."
        )
    elif reminder_type == "APPOINTMENT_2H":
        return (
            f"{greeting}\n\n"
            f"Your appointment{title_suffix} at *{clinic_name}* is coming up in about 2 hours today at *{time_str}*.\n\n"
            f"We look forward to seeing you!"
        )
    else:
        return (
            f"{greeting}\n\n"
            f"Reminder: You have an upcoming appointment{title_suffix} at *{clinic_name}* on *{date_str}* at *{time_str}*."
        )
