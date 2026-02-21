#!/usr/bin/env python3
"""
Test script to verify email configuration
Run this to test if your email settings are correct before deploying
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from backend.config import Config

load_dotenv()


def test_email():
    """Send a test email to verify configuration"""
    print("Testing email configuration...")
    print(f"Host: {Config.EMAIL_HOST}")
    print(f"Port: {Config.EMAIL_PORT}")
    print(f"From: {Config.EMAIL_USERNAME}")
    print(f"To: {Config.EMAIL_RECIPIENT}")
    print()

    email_username = Config.EMAIL_USERNAME
    email_password = Config.EMAIL_PASSWORD
    email_recipient = Config.EMAIL_RECIPIENT
    if not email_username or not email_password or not email_recipient:
        print("Missing required email settings.")
        print("Please set EMAIL_USERNAME, EMAIL_PASSWORD, and EMAIL_RECIPIENT.")
        return False

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "ECC Sheet - Test Email"
        msg["From"] = email_username
        msg["To"] = email_recipient

        # Create HTML content
        html_content = """
        <html>
        <body>
            <h2>ECC Sheet Email Test</h2>
            <p>This is a test email from the ECC Sheet application.</p>
            <p>If you receive this, your email configuration is working correctly!</p>
        </body>
        </html>
        """

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Send email
        print("Connecting to SMTP server...")
        with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT) as server:
            print("Starting TLS...")
            server.starttls()

            print("Logging in...")
            server.login(email_username, email_password)

            print("Sending email...")
            server.send_message(msg)

        print()
        print("Test email sent successfully!")
        print(f"Check {email_recipient} for the test message.")

    except Exception as e:
        print()
        print("Error sending email:")
        print(f"{e!s}")
        print()
        print("Common issues:")
        print(
            "- Gmail: Make sure you're using an App Password, not your regular password"
        )
        print("- Check EMAIL_HOST and EMAIL_PORT in .env")
        print("- Verify EMAIL_USERNAME and EMAIL_PASSWORD are correct")
        print("- Some email providers require additional security settings")
        return False

    return True


if __name__ == "__main__":
    test_email()
