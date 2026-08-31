from typing import Optional
from app.core.logging import logger


def log_auth_event(
    event_type: str,
    email: Optional[str] = None,
    user_id: Optional[str] = None,
    clinic_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """
    Lightweight authentication and authorization audit logger.
    Records security-relevant events without storing credentials, tokens, or PII.
    """
    safe_email = email.strip().lower() if email else "-"
    safe_user_id = str(user_id) if user_id else "-"
    safe_clinic_id = str(clinic_id) if clinic_id else "-"
    safe_detail = detail if detail else "-"

    logger.info(
        "AUTH_AUDIT | event=%s | email=%s | user_id=%s | clinic_id=%s | detail=%s",
        event_type,
        safe_email,
        safe_user_id,
        safe_clinic_id,
        safe_detail,
    )

