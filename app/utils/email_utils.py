import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from dotenv import load_dotenv

from app.config import EMAIL_HOST, EMAIL_PASSWORD, EMAIL_PORT, EMAIL_USER

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
        # ✅ Generate HTML with passed values
        html = get_welcome_template(
            email=to_email,
            password=password,
            login_url="http://localhost:3000/login"
        )

        print("📧 Sending email to:", to_email)
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
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())

        print("✅ Email sent successfully to", to_email)

        return True

    except Exception as e:
        print("❌ Error sending email:", e)
        return False