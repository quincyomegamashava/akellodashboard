"""Shared recipient resolution for revenue report / FY digest emails."""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.models import AppSetting, User

PRIVILEGE_NAME = "Revenue Reports"


def parse_email_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    seen = set()
    out: List[str] = []
    for part in str(raw).replace(";", ",").split(","):
        email = part.strip()
        if not email or "@" not in email:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(email)
    return out


def resolve_revenue_report_recipients(
    recipient_mode: Optional[str] = None,
    custom_list: Optional[str] = None,
) -> Tuple[List[str], str]:
    """
    Resolve recipient emails from AppSetting (or overrides).

    Modes:
      - privilege_holders: Admins + users with Revenue Reports privilege
      - custom_list: comma-separated AppSetting revenue_reports_email_recipients
      - custom_group_later: legacy pending stub (no send)
    """
    mode = (
        recipient_mode
        if recipient_mode is not None
        else (AppSetting.get_value("revenue_reports_email_recipient_mode", "custom_group_later") or "custom_group_later")
    ).strip().lower()

    if mode == "custom_group_later":
        return [], "recipients_pending_configuration"

    if mode == "custom_list":
        raw = (
            custom_list
            if custom_list is not None
            else AppSetting.get_value("revenue_reports_email_recipients", "")
        )
        emails = parse_email_list(raw)
        if not emails:
            return [], "custom_list_empty"
        return emails, ""

    if mode == "privilege_holders":
        emails: List[str] = []
        seen = set()
        try:
            users = User.query.filter(User.email.isnot(None)).all()
        except Exception:
            return [], "user_query_failed"
        for user in users:
            email = (user.email or "").strip()
            if not email or "@" not in email:
                continue
            role = (getattr(user, "userRole", None) or "").strip()
            allowed = role == "Admin"
            if not allowed:
                try:
                    allowed = bool(user.has_privilege(PRIVILEGE_NAME))
                except Exception:
                    allowed = False
            if not allowed:
                continue
            key = email.lower()
            if key in seen:
                continue
            seen.add(key)
            emails.append(email)
        if not emails:
            return [], "no_privilege_holders_with_email"
        return emails, ""

    return [], f"unsupported_recipient_mode:{mode}"
