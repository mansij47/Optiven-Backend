import base64
import logging
import os
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


def _get_str_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None:
        return default
    trimmed = str(value).strip()
    return trimmed or default


def _get_int_env(key: str, default: int) -> int:
    value = _get_str_env(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_brevo_sender() -> tuple[Optional[dict], Optional[str]]:
    api_key = _get_str_env("BREVO_API_KEY")
    from_email = _get_str_env("BREVO_FROM_EMAIL") or _get_str_env("EMAIL_USER")
    sender_name = _get_str_env("BREVO_SENDER_NAME", "Optiven")

    if not api_key:
        return None, "BREVO_API_KEY is not configured"
    if not api_key.startswith("xkeysib-"):
        return None, "BREVO_API_KEY is invalid for Brevo HTTP API"
    if not from_email:
        return None, "BREVO_FROM_EMAIL is not configured"

    return {"name": sender_name or "Optiven", "email": from_email}, None


def create_base64_attachment(
    file_path: str,
    attachment_name: str,
) -> tuple[Optional[dict], Optional[str]]:
    if not file_path:
        return None, None

    if not os.path.exists(file_path):
        return None, f"Attachment not found: {file_path}"

    try:
        with open(file_path, "rb") as file_handle:
            encoded = base64.b64encode(file_handle.read()).decode("utf-8")
        return {"name": attachment_name, "content": encoded}, None
    except Exception as exc:
        return None, f"Attachment encoding failed: {exc}"


def send_email_via_brevo(
    to_email: str,
    subject: str,
    html_content: str,
    attachment: Optional[dict] = None,
) -> tuple[bool, Optional[str], Optional[dict]]:
    if not str(html_content or "").strip():
        error_message = "Email HTML content is empty"
        logger.error("Brevo payload blocked recipient=%s error=%s", to_email, error_message)
        return False, error_message, None

    sender, sender_error = _get_brevo_sender()
    if sender_error:
        logger.error("Brevo sender validation failed recipient=%s error=%s", to_email, sender_error)
        return False, sender_error, None

    api_key = _get_str_env("BREVO_API_KEY")
    api_url = _get_str_env("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email")
    timeout_seconds = _get_int_env("EMAIL_TIMEOUT_SECONDS", 20)

    payload = {
        "sender": sender,
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    if attachment:
        payload["attachment"] = [attachment]

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        response = httpx.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )

        if response.status_code >= 400:
            logger.error(
                "Brevo rejected recipient=%s status=%s body=%s",
                to_email,
                response.status_code,
                response.text[:500],
            )
            return False, f"Brevo API error {response.status_code}: {response.text[:300]}", None

        message_id = None
        try:
            response_data = response.json() if response.content else {}
            if isinstance(response_data, dict):
                message_id = response_data.get("messageId")
        except Exception:
            message_id = None

        provider_info = {
            "provider": "brevo",
            "accepted_by_provider": True,
            "status_code": response.status_code,
            "message_id": message_id,
        }
        logger.info(
            "Brevo accepted recipient=%s status=%s message_id=%s",
            to_email,
            response.status_code,
            message_id,
        )
        return True, None, provider_info
    except Exception as exc:
        logger.exception("Brevo request exception recipient=%s error=%s", to_email, exc)
        return False, f"Brevo request failed: {exc}", None
