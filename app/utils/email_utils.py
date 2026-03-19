import smtplib
import os
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders


from app.config import EMAIL_HOST, EMAIL_PASSWORD, EMAIL_PORT, EMAIL_TIMEOUT_SECONDS, EMAIL_USER, LOGIN_URL


def _missing_email_config_keys() -> list:
  missing = []
  if not EMAIL_HOST:
    missing.append("EMAIL_HOST")
  if not EMAIL_USER:
    missing.append("EMAIL_USER")
  if not EMAIL_PASSWORD:
    missing.append("EMAIL_PASSWORD")
  if not EMAIL_PORT:
    missing.append("EMAIL_PORT")
  return missing

# 👇 Your new HTML template function
def get_welcome_template(email: str, password: str, login_url: str) -> str:
    return f""" 
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Welcome Email</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: #f4f6fa;">
  <table align="center" width="100%" cellpadding="0" cellspacing="0"
    style="max-width: 600px; background-color: #ffffff; margin: 20px auto; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
    <tr>
      <td>
        <!-- 👇 Jinja will link this as inline image -->
        <img src="cid:welcome_image" alt="Inventory System" style="width: 100%; height: auto;" />
      </td>
    </tr>
    <tr>
      <td style="padding: 10px 20px 20px 20px;">
        <h2 style="color: #1d3557; margin-top:0;">👋 Welcome to Inventory Management System</h2>

    

        <p style="color: #555;">Your store setup is complete! We've created your personalized dashboard with all the tools you need to manage your online business. Use the credentials below to access your store administration panel.</p>

        <div style="background-color: #f1f3f8; padding: 20px; border-radius: 6px; text-align: center; margin: 20px 0;">
          <p style="margin: 0; font-weight: bold; color: #1d3557;">🔐 Your Login Credentials:</p>
          <p style="font-size: 20px; font-weight: bold; margin: 10px 0; color: #2c3e50;">{ password}</p>
          <p style="color: #555;"><a href="mailto:{ email }" style="color: #1a73e8;">{email}</a></p>
        </div>

         <div style="text-align: center; margin: 30px 0;">
          <a href="{ login_url }" style="background-color: #2d69f6; color: white; text-decoration: none; padding: 12px 24px; border-radius: 5px; font-weight: bold;">🔑 Login to Your Store</a>
        </div>

        <p style="font-size: 14px; color: #999; text-align: center;">We recommend changing your password after your first login.</p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;" />

        <p style="font-size: 12px; color: #aaa; text-align: center;">
          If you received this email by mistake, you can ignore it safely.<br />
          — Optiven
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
    """

def send_welcome_email(to_email: str, password: str) -> bool:
    try:
        missing = _missing_email_config_keys()
        if missing:
            print(f" Error sending email: missing SMTP config: {', '.join(missing)}")
            return False

        # ✅ Generate HTML with passed values
        html = get_welcome_template(
            email=to_email,
            password=password,
            login_url= LOGIN_URL
        )

        print(" Sending email to:", to_email)
        # Create email
        msg = MIMEMultipart("related")
        msg["Subject"] = "Welcome to Inventory Management System"
        msg["From"] = EMAIL_USER
        msg["To"] = to_email

        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html, "html"))
        msg.attach(alternative)

        # Attach the image with CID reference
        with open("assets/image.jpeg", "rb") as image_file:
            image = MIMEImage(image_file.read(), name="image.jpeg")
            image.add_header("Content-ID", "<welcome_image>")
            image.add_header("Content-Disposition", "inline", filename="image.jpeg")
            msg.attach(image)

        # Send
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=EMAIL_TIMEOUT_SECONDS) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())

        print(" Email sent successfully to", to_email)

        return True

    except Exception as e:
        print(" Error sending email:", e)
        return False

# 👇 Purchase Order Email Template
def get_purchase_order_template(order_data: dict, custom_message: str = None) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Purchase Order</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: #f4f6fa;">
  <table align="center" width="100%" cellpadding="0" cellspacing="0"
    style="max-width: 600px; background-color: #ffffff; margin: 20px auto; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
    <tr>
      <td style="background-color: #1d3557; color: white; padding: 20px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">📋 Purchase Order</h1>
        <p style="margin: 5px 0 0; font-size: 16px;">Order ID: {order_data.get('order_id', 'N/A')}</p>
      </td>
    </tr>
    <tr>
      <td style="padding: 20px;">
        <p style="color: #555; margin-bottom: 20px;">Dear {order_data.get('vendor_name', 'Vendor')},</p>

        {f'<div style="background-color: #e8f4fd; padding: 15px; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid #2d69f6;"><p style="margin: 0; color: #1d3557;">{custom_message}</p></div>' if custom_message else ''}

        <p style="color: #555;">We are pleased to send you the following purchase order details:</p>

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
            <tr>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{order_data.get('product_name', 'N/A')}</td>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">{order_data.get('expected_quantity', 'N/A')} {order_data.get('unit', '')}</td>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057;">₹{order_data.get('unit_price', 'N/A')}</td>
              <td style="border: 1px solid #dee2e6; padding: 12px; color: #495057; font-weight: bold;">₹{order_data.get('amount', 'N/A')}</td>
            </tr>
          </tbody>
        </table>

        <div style="background-color: #f1f3f8; padding: 15px; border-radius: 6px; margin: 20px 0;">
          <p style="margin: 0; font-weight: bold; color: #1d3557;">📅 Delivery Details:</p>
          <p style="margin: 5px 0; color: #555;">Expected Delivery Date: {order_data.get('delivery_date', 'N/A')}</p>
          <p style="margin: 5px 0; color: #555;">Warranty: {order_data.get('warranty_tenure', 'N/A')} {order_data.get('warranty_unit', '')}</p>
        </div>

        <p style="color: #555;">Please confirm receipt of this purchase order and provide the estimated delivery timeline.</p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;" />

        <p style="font-size: 12px; color: #aaa; text-align: center;">
          Thank you for your partnership.<br />
          — Optiven Procurement Team
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
    """


def send_purchase_order_email(order_data: dict, recipient_emails: list, subject: str = "Purchase Order", custom_message: str = None, pdf_path: str = None) -> dict:
    """
    Send purchase order email to vendor(s) with optional PDF attachment
    
    Args:
        order_data: Dictionary containing purchase order details
        recipient_emails: List of email addresses to send to
        subject: Email subject line
        custom_message: Optional custom message to include in email
        pdf_path: Optional path to PDF file to attach
    
    Returns:
        Dictionary with success status and details
    """
    missing = _missing_email_config_keys()
    if missing:
      return {
        "success": False,
        "total_emails": len(recipient_emails),
        "successful_emails": 0,
        "failed_emails": len(recipient_emails),
        "details": [
          {
            "email": email,
            "status": "failed",
            "error": f"Missing SMTP config: {', '.join(missing)}",
          }
          for email in recipient_emails
        ],
      }

    results = []
    
    for email in recipient_emails:
        try:
            # Generate HTML email content
            html = get_purchase_order_template(order_data, custom_message)

            print(f"📧 Sending purchase order email to: {email}")
            
            # Create email
            msg = MIMEMultipart("related")
            msg["Subject"] = f"{subject} - {order_data.get('order_id', 'N/A')}"
            msg["From"] = EMAIL_USER
            msg["To"] = email

            alternative = MIMEMultipart("alternative")
            alternative.attach(MIMEText(html, "html"))
            msg.attach(alternative)

            # Attach PDF if provided
            if pdf_path and os.path.exists(pdf_path):
                try:
                    with open(pdf_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= "PurchaseOrder_{order_data.get("order_id", "Unknown")}.pdf"'
                    )
                    msg.attach(part)
                    print(f"📎 PDF attachment added: {pdf_path}")
                except Exception as attachment_error:
                    print(f"⚠️ Failed to attach PDF: {attachment_error}")

            # Send email
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=EMAIL_TIMEOUT_SECONDS) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_USER, email, msg.as_string())

            print(f"✅ Purchase order email sent successfully to {email}")
            results.append({"email": email, "status": "success"})

        except (smtplib.SMTPException, OSError, socket.timeout) as e:
            print(f"❌ Error sending purchase order email to {email}: {e}")
            results.append({"email": email, "status": "failed", "error": str(e)})
        except Exception as e:
            print(f"❌ Unexpected error sending purchase order email to {email}: {e}")
            results.append({"email": email, "status": "failed", "error": str(e)})
    
    success_count = len([r for r in results if r["status"] == "success"])
    total_count = len(results)
    
    return {
        "success": success_count > 0,
        "total_emails": total_count, 
        "successful_emails": success_count,
        "failed_emails": total_count - success_count,
        "details": results
    }