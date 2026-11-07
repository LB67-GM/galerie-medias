"""Envoi du lien de réinitialisation. Aucun mot de passe n’est journalisé."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage


def smtp_password(value: str) -> str:
    # Google présente le mot de passe d’application en quatre blocs.
    return "".join(str(value or "").split())


def smtp_configured(settings: dict) -> bool:
    host = str(settings.get("smtp_host") or "").strip()
    sender = str(settings.get("smtp_from") or settings.get("smtp_user") or "").strip()
    return bool(host and sender)


def public_base(settings: dict, request_base: str) -> str:
    raw = str(settings.get("public_url") or "").strip().rstrip("/")
    if raw.startswith("https://") or raw.startswith("http://"):
        return raw
    return (request_base or "").strip().rstrip("/")


def send_password_reset(settings: dict, recipient: str, link: str) -> None:
    host = str(settings.get("smtp_host") or "").strip()
    sender = str(settings.get("smtp_from") or settings.get("smtp_user") or "").strip()
    user = str(settings.get("smtp_user") or "").strip()
    password = smtp_password(str(settings.get("smtp_password") or ""))
    try:
        port = int(str(settings.get("smtp_port") or "587"))
    except ValueError:
        port = 587
    if not host or not sender:
        raise RuntimeError("smtp")
    message = EmailMessage()
    message["Subject"] = "Galerie Médias — mot de passe / password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Bonjour,\n\n"
        "Pour choisir un nouveau mot de passe, ouvrez ce lien. Il est valable une heure :\n"
        f"{link}\n\n"
        "Si vous n’êtes pas à l’origine de cette demande, ignorez ce message.\n\n"
        "----\n\n"
        "Hello,\n\n"
        "To choose a new password, open this link. It is valid for one hour:\n"
        f"{link}\n\n"
        "If you did not ask for this, you can ignore this message.\n"
    )
    if port == 465:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)
    try:
        smtp.ehlo()
        if port != 465 and str(settings.get("smtp_tls") or "1") != "0":
            smtp.starttls()
            smtp.ehlo()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)
    finally:
        try:
            smtp.quit()
        except (OSError, smtplib.SMTPException):
            pass
