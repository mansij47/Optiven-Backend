import html
import logging
import os
from typing import Any
from urllib.parse import urlencode

from app.config import LOGIN_URL, SET_PASSWORD_URL
from app.utils.email_service import create_base64_attachment, send_email_via_brevo


logger = logging.getLogger(__name__)


def _get_str_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None:
        return default
    trimmed = str(value).strip()
    return trimmed or default


def _missing_brevo_config_keys() -> list[str]:
    missing = []
    if not _get_str_env("BREVO_API_KEY"):
        missing.append("BREVO_API_KEY")
    if not (_get_str_env("BREVO_FROM_EMAIL") or _get_str_env("EMAIL_USER")):
        missing.append("BREVO_FROM_EMAIL")
    return missing


def _safe_text(value: Any, fallback: str = "N/A") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return html.escape(text)


def _purchase_order_rows(order_data: dict) -> str:
    items = order_data.get("items") or []
    rows = []

    if isinstance(items, list) and items:
        for item in items:
            if not isinstance(item, dict):
                continue
            item_name = _safe_text(item.get("item_name") or item.get("product_name"))
            quantity = _safe_text(item.get("quantity") or order_data.get("expected_quantity"))
            unit_price = _safe_text(item.get("unit_price"))
            total_price = _safe_text(item.get("total_price") or item.get("amount"))
            rows.append(
                f"""
                <tr>
                  <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{item_name}</td>
                  <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{quantity}</td>
                  <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{unit_price}</td>
                  <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057; font-weight: bold;">{total_price}</td>
                </tr>
                """
            )

    if rows:
        return "".join(rows)

    product_name = _safe_text(order_data.get("product_name"))
    quantity = _safe_text(order_data.get("expected_quantity"))
    unit = _safe_text(order_data.get("unit"), "")
    if unit:
        quantity = f"{quantity} {unit}"
    unit_price = _safe_text(order_data.get("unit_price"))
    amount = _safe_text(order_data.get("amount"))
    return f"""
            <tr>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{product_name}</td>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{quantity}</td>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{unit_price}</td>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057; font-weight: bold;">{amount}</td>
            </tr>
    """


def _build_set_password_url(token: str | None, email: str | None = None) -> str:
    if not token:
        return SET_PASSWORD_URL

    query_payload = {"token": token}
    if email:
        query_payload["email"] = email

    query = urlencode(query_payload)
    separator = "&" if "?" in SET_PASSWORD_URL else "?"
    return f"{SET_PASSWORD_URL}{separator}{query}"


def get_welcome_template(
    email: str,
    password: str | None,
    login_url: str,
    set_password_url: str | None = None,
    admin_name: str | None = None,
    store_name: str | None = None,
    store_id: str | None = None,
    account_type: str = "store_admin",
    employee_role: str | None = None,
) -> str:
    safe_email = _safe_text(email)
    safe_password = _safe_text(password) if password else ""
    safe_login_url = html.escape(login_url or "")
    safe_set_password_url = html.escape(set_password_url or "")
    safe_admin_name = _safe_text(admin_name, "Admin")
    safe_store_name = _safe_text(store_name, "Your Store")
    safe_store_id = _safe_text(store_id, "N/A")
    safe_employee_role = _safe_text(employee_role, "Employee")

    is_employee_onboarding = account_type == "employee"

    if is_employee_onboarding:
        context_title = "Employee Access Details"
        intro_text = "Your employee account is ready. Please use the details below to access your account."
        header_subtitle = f"You have been added as a {safe_employee_role} user for {safe_store_name}."
        context_role_line = f"<p style=\"margin: 3px 0; color: #4b5563; font-size: 14px;\"><strong>Role:</strong> {safe_employee_role}</p>"
    else:
        context_title = "Store Access Details"
        intro_text = "Your store admin account is ready. Please finish setup using the details below."
        header_subtitle = f"You have been added as the store admin for {safe_store_name}."
        context_role_line = ""

    context_block = f"""
    <div style="background-color: #f7f9fc; border: 1px solid #e8ecf3; padding: 14px; border-radius: 6px; margin: 16px 0 20px 0;">
        <p style="margin: 0 0 8px 0; font-weight: 600; color: #1d3557;">{context_title}</p>
        <p style="margin: 3px 0; color: #4b5563; font-size: 14px;"><strong>Name:</strong> {safe_admin_name}</p>
        {context_role_line}
        <p style="margin: 3px 0; color: #4b5563; font-size: 14px;"><strong>Store:</strong> {safe_store_name}</p>
        <p style="margin: 3px 0; color: #4b5563; font-size: 14px;"><strong>Store ID:</strong> {safe_store_id}</p>
        <p style="margin: 3px 0; color: #4b5563; font-size: 14px;"><strong>Login Email:</strong> {safe_email}</p>
    </div>
    """

    if safe_set_password_url:
        auth_block = f"""
        <div style="background-color: #f1f3f8; padding: 20px; border-radius: 6px; text-align: center; margin: 20px 0;">
            <p style="margin: 0 0 8px 0; font-weight: bold; color: #1d3557;">Set Your Password</p>
            <p style="margin: 0 0 14px 0; color: #555;">Click the button below to create your password and activate your account.</p>
            <a href="{safe_set_password_url}" style="background-color: #2d69f6; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 5px; font-weight: bold; display: inline-block;">Set Password</a>
        </div>
        <p style="font-size: 14px; color: #666; margin: 14px 0 0 0;">If the button does not work, use this link:</p>
        <p style="font-size: 14px; margin: 8px 0 0 0;"><a href="{safe_set_password_url}" style="color: #1a73e8; text-decoration: underline;">Open set-password link</a></p>
        """
    else:
        credential_title = "Employee Login Credentials" if is_employee_onboarding else "Login Credentials"
        auth_block = f"""
        <div style="background-color: #f1f3f8; padding: 20px; border-radius: 6px; text-align: center; margin: 20px 0;">
            <p style="margin: 0; font-weight: bold; color: #1d3557;">{credential_title}</p>
            <p style="font-size: 18px; font-weight: bold; margin: 10px 0 6px; color: #2c3e50;">{safe_password}</p>
            <p style="margin: 0; color: #555;"><a href="mailto:{safe_email}" style="color: #1a73e8;">{safe_email}</a></p>
        </div>

        <div style="text-align: center; margin: 28px 0;">
            <a href="{safe_login_url}" style="background-color: #2d69f6; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 5px; font-weight: bold;">Login to Optiven</a>
        </div>

        <p style="font-size: 14px; color: #666;">Please change your password after your first login.</p>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <title>Welcome Email</title>
</head>
<body style="margin: 0; padding: 0 0 24px 0; font-family: 'Segoe UI', sans-serif; background-color: #f4f6fa;">
    <table align="center" width="100%" cellpadding="0" cellspacing="0"
        style="max-width: 600px; background-color: #ffffff; margin: 20px auto; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.08);">
        <tr>
            <td style="background: linear-gradient(135deg, #1d3557, #2d69f6); color: #ffffff; padding: 28px 24px;">
                <h2 style="margin: 0 0 8px 0;">Welcome, {safe_admin_name}</h2>
                <p style="margin: 0; opacity: 0.92;">{header_subtitle}</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 24px 24px 36px 24px;">
                <p style="color: #555; margin-top: 0;">{intro_text}</p>

                {context_block}

                {auth_block}

                <hr style="border: none; border-top: 1px solid #eee; margin: 28px 0;" />

                <p style="font-size: 12px; color: #999; text-align: center; margin: 0;">
                    If you received this email by mistake, you can ignore it safely.<br />
                    Optiven Team
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
        """

def send_welcome_email(
    to_email: str,
    password: str | None = None,
    set_password_token: str | None = None,
    admin_name: str | None = None,
    store_name: str | None = None,
    store_id: str | None = None,
    account_type: str = "store_admin",
    employee_role: str | None = None,
) -> bool:
    recipient = str(to_email or "").strip().lower()
    

    if not recipient:
        logger.warning("Welcome email failed recipient=missing reason=recipient email is required")
        return False

    try:
        missing = _missing_brevo_config_keys()
        if missing:
            reason = f"missing_config:{','.join(missing)}"
            logger.warning("Welcome email blocked recipient=%s reason=%s", recipient, reason)
            return False

        set_password_url = _build_set_password_url(set_password_token, recipient) if set_password_token else None
        html = get_welcome_template(
            email=to_email,
            password=password,
            login_url=LOGIN_URL,
            set_password_url=set_password_url,
            admin_name=admin_name,
            store_name=store_name,
            store_id=store_id,
            account_type=account_type,
            employee_role=employee_role,
        )

        if account_type == "employee":
            subject = f"Welcome to {store_name or 'Optiven'} - Your {employee_role or 'Employee'} account is ready"
        else:
            subject = f"Welcome to {store_name or 'Optiven'} - Set up your admin account"

        sent, send_error, provider_info = send_email_via_brevo(
            to_email=to_email,
            subject=subject,
            html_content=html,
        )

        if not sent:
            logger.warning("Welcome email send failed recipient=%s error=%s", to_email, send_error)
            return False

        logger.info("Welcome email sent recipient=%s", to_email)

        return True

    except Exception as e:
        logger.exception("Welcome email exception recipient=%s error=%s", to_email, e)
        return False


def get_purchase_order_template(order_data: dict, custom_message: str | None = None) -> str:
    safe_vendor_name = _safe_text(order_data.get("vendor_name"), "Vendor")
    safe_order_id = _safe_text(order_data.get("order_id"))
    safe_delivery_date = _safe_text(order_data.get("delivery_date"))
    safe_warranty_tenure = _safe_text(order_data.get("warranty_tenure"))
    safe_warranty_unit = _safe_text(order_data.get("warranty_unit"), "")
    safe_message = ""
    custom_message_text = str(custom_message or "").strip()
    custom_message_lower = custom_message_text.lower()
    has_custom_greeting = custom_message_lower.startswith("dear ")
    has_custom_intro = "please find attached" in custom_message_lower or "purchase order" in custom_message_lower

    greeting_block = ""
    if not has_custom_greeting:
        greeting_block = f'<p style="color: #555; margin-bottom: 20px;">Dear {safe_vendor_name},</p>'

    intro_block = ""
    if not has_custom_intro:
        intro_block = '<p style="color: #555;">Please find the purchase order details below.</p>'

    if custom_message:
        safe_message_body = html.escape(custom_message).replace("\n", "<br />")
        safe_message = f"""
        <div style="background-color: #e8f4fd; padding: 15px; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid #2d69f6;">
          <p style="margin: 0; color: #1d3557;">{safe_message_body}</p>
        </div>
        """

    warranty_display = safe_warranty_tenure
    if safe_warranty_unit:
        warranty_display = f"{warranty_display} {safe_warranty_unit}".strip()

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Purchase Order</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: #f4f6fa;">
  <table align="center" width="100%" cellpadding="0" cellspacing="0"
    style="max-width: 700px; background-color: #ffffff; margin: 20px auto; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.08);">
    <tr>
      <td style="background-color: #1d3557; color: #ffffff; padding: 20px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">Purchase Order</h1>
        <p style="margin: 5px 0 0; font-size: 16px;">Order ID: {safe_order_id}</p>
      </td>
    </tr>
    <tr>
      <td style="padding: 20px;">
                {greeting_block}

        {safe_message}

                {intro_block}

        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
          <thead>
            <tr style="background-color: #f8f9fa;">
              <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; color: #495057;">Product Name</th>
              <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; color: #495057;">Quantity</th>
              <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; color: #495057;">Unit Price</th>
              <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; color: #495057;">Total</th>
            </tr>
          </thead>
          <tbody>
            {_purchase_order_rows(order_data)}
          </tbody>
        </table>

        <div style="background-color: #f1f3f8; padding: 15px; border-radius: 6px; margin: 20px 0;">
          <p style="margin: 0 0 8px 0; font-weight: bold; color: #1d3557;">Delivery Details</p>
          <p style="margin: 4px 0; color: #555;">Expected Delivery Date: {safe_delivery_date}</p>
          <p style="margin: 4px 0; color: #555;">Warranty: {warranty_display}</p>
        </div>

        <p style="color: #555;">Please confirm receipt of this purchase order and share your expected delivery timeline.</p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;" />

        <p style="font-size: 12px; color: #999; text-align: center;">
          Thank you for your partnership.<br />
          Optiven Procurement Team
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
    """


def send_purchase_order_email(
    order_data: dict,
    recipient_emails: list,
    subject: str = "Purchase Order",
    custom_message: str | None = None,
    pdf_path: str | None = None,
) -> dict:
    normalized_recipients = []
    seen_recipients = set()
    for raw_email in recipient_emails or []:
        email = str(raw_email or "").strip().lower()
        if not email or email in seen_recipients:
            continue
        normalized_recipients.append(email)
        seen_recipients.add(email)

    if not normalized_recipients:
        return {
            "success": False,
            "total_emails": 0,
            "successful_emails": 0,
            "failed_emails": 0,
            "successful_email_list": [],
            "failed_email_list": [],
            "details": [],
            "attachment_included": False,
            "attachment_error": None,
        }

    missing = _missing_brevo_config_keys()
    if missing:
        error_message = f"Missing email config: {', '.join(missing)}"
        logger.warning(
            "Purchase order email blocked order_id=%s reason=%s",
            order_data.get("order_id"),
            error_message,
        )
        return {
            "success": False,
            "total_emails": len(normalized_recipients),
            "successful_emails": 0,
            "failed_emails": len(normalized_recipients),
            "successful_email_list": [],
            "failed_email_list": [
                {
                    "email": email,
                    "error": error_message,
                }
                for email in normalized_recipients
            ],
            "details": [
                {
                    "email": email,
                    "status": "failed",
                    "error": error_message,
                }
                for email in normalized_recipients
            ],
            "attachment_included": False,
            "attachment_error": None,
        }

    attachment = None
    attachment_error = None
    if pdf_path:
        attachment_name = f"PurchaseOrder_{order_data.get('order_id', 'Unknown')}.pdf"
        attachment, attachment_error = create_base64_attachment(pdf_path, attachment_name)
        if attachment_error:
            logger.warning(
                "Purchase order attachment failed order_id=%s error=%s",
                order_data.get("order_id"),
                attachment_error,
            )

    html_content = get_purchase_order_template(order_data, custom_message)
    order_id = str(order_data.get("order_id") or "").strip()
    base_subject = str(subject or "Purchase Order").strip()
    if not base_subject:
        base_subject = "Purchase Order"

    if order_id and order_id.lower() not in base_subject.lower():
        email_subject = f"{base_subject} - {order_id}"
    else:
        email_subject = base_subject
    results = []

    for recipient in normalized_recipients:
        logger.info("Purchase order email start order_id=%s recipient=%s", order_data.get("order_id"), recipient)
        try:
            sent, error_message, provider_info = send_email_via_brevo(
                to_email=recipient,
                subject=email_subject,
                html_content=html_content,
                attachment=attachment,
            )
            if sent:
                provider = (provider_info or {}).get("provider", "unknown")
                message_id = (provider_info or {}).get("message_id")
                logger.info(
                    "Purchase order email success order_id=%s recipient=%s provider=%s message_id=%s",
                    order_data.get("order_id"),
                    recipient,
                    provider,
                    message_id,
                )
                results.append(
                    {
                        "email": recipient,
                        "status": "success",
                        "method": provider,
                        "message_id": message_id,
                    }
                )
            else:
                logger.warning(
                    "Purchase order email failed order_id=%s recipient=%s error=%s",
                    order_data.get("order_id"),
                    recipient,
                    error_message,
                )
                results.append(
                    {
                        "email": recipient,
                        "status": "failed",
                        "error": error_message or "Unknown email provider error",
                    }
                )
        except Exception as exc:
            logger.exception(
                "Purchase order email exception order_id=%s recipient=%s error=%s",
                order_data.get("order_id"),
                recipient,
                exc,
            )
            results.append(
                {
                    "email": recipient,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    success_count = len([result for result in results if result["status"] == "success"])
    total_count = len(results)
    success_email_list = [
        result.get("email")
        for result in results
        if result.get("status") == "success" and result.get("email")
    ]
    failed_email_list = [
        {
            "email": result.get("email"),
            "error": result.get("error") or "Unknown email provider error",
        }
        for result in results
        if result.get("status") == "failed"
    ]
    return {
        "success": success_count > 0,
        "total_emails": total_count,
        "successful_emails": success_count,
        "failed_emails": total_count - success_count,
        "successful_email_list": success_email_list,
        "failed_email_list": failed_email_list,
        "details": results,
        "attachment_included": attachment is not None,
        "attachment_error": attachment_error,
    }
