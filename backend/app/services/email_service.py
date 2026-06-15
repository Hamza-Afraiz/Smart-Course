"""SMTP email delivery — Mailhog in dev, real provider in prod."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def _send_sync(*, to: str, subject: str, body: str) -> None:
    if not settings.smtp_enabled:
        logger.info("[email disabled] to=%s subject=%s", to, subject)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def send_email(*, to: str, subject: str, body: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, lambda: _send_sync(to=to, subject=subject, body=body)
    )
