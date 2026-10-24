"""
email_service.py
-----------------
Sends transactional emails via Gmail SMTP:
  - Certification confirmation (successful registration)
  - Violation warning (a submission was caught as a copy)
  - Account withheld notice (3rd violation reached)

Requires in .env:
    GMAIL_ADDRESS=your_gmail@gmail.com
    GMAIL_APP_PASSWORD=your_16_char_app_password

Get an App Password from: myaccount.google.com/apppasswords
(requires 2-Step Verification enabled on the Gmail account)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _send(to_email: str, subject: str, body_html: str) -> bool:
    """
    Sends an email. Returns True on success, False on failure
    (failures are logged but never raised — email is best-effort
    and should never break the certification flow).
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print(f"  ⚠ Email not configured — would have sent '{subject}' to {to_email}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Artchain <{GMAIL_ADDRESS}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        print(f"  ✓ Email sent: '{subject}' -> {to_email}")
        return True
    except Exception as e:
        print(f"  ⚠ Email failed to send: {e}")
        return False


def send_certification_email(to_email: str, title: str, author: str, phash: str,
                              image_cid: str, tx_hash: str):
    subject = f"Artchain — '{title}' has been certified"
    body = f"""
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2>Your artwork is now certified on-chain</h2>
      <p><b>Title:</b> {title}</p>
      <p><b>Author:</b> {author}</p>
      <p><b>pHash (fingerprint):</b> {phash}</p>
      <p><b>Image ID:</b> {image_cid}</p>
      <p><b>Blockchain transaction (local Hardhat chain):</b> {tx_hash}</p>
      <p>This certificate is permanent and cannot be altered or removed.</p>
    </div>
    """
    return _send(to_email, subject, body)


def send_violation_email(to_email: str, attempted_title: str, matched_title: str,
                          matched_author: str, violation_count: int):
    subject = f"Artchain — submission flagged as a possible copy"
    body = f"""
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2>Your submission was flagged</h2>
      <p>Your upload "<b>{attempted_title}</b>" was detected as matching an
         existing registered artwork: "<b>{matched_title}</b>" by {matched_author}.</p>
      <p>It was <b>not</b> certified.</p>
      <p>This is violation <b>{violation_count} of 3</b> on your account.
         Repeated violations will result in your account being withheld.</p>
    </div>
    """
    return _send(to_email, subject, body)


def send_withheld_email(to_email: str):
    subject = "Artchain — your account has been withheld"
    body = """
    <div style="font-family: sans-serif; max-width: 500px;">
      <h2>Your account has been withheld</h2>
      <p>You have reached 3 flagged submissions for copied artwork.
         Your account can no longer submit new certifications.</p>
      <p>If you believe this is an error, please contact the platform administrator.</p>
    </div>
    """
    return _send(to_email, subject, body)