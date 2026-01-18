"""
Email utility for sending transactional emails.

In development mode, emails are logged to console instead of being sent.
In production, configure SMTP settings in environment variables.
"""
import os
import logging
import smtplib
import socket
from flask import current_app, url_for

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, html: str = None) -> bool:
    """
    Send an email.

    In development mode (no SMTP configured), logs to console.
    In production, sends via SMTP.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text email body
        html: Optional HTML email body

    Returns:
        True if email was sent (or logged) successfully, False otherwise
    """
    smtp_host = os.environ.get('SMTP_HOST')

    if not smtp_host:
        # Development mode: log email to console
        logger.info("=" * 60)
        logger.info("EMAIL (not sent - dev mode)")
        logger.info(f"To: {to}")
        logger.info(f"Subject: {subject}")
        logger.info("-" * 60)
        logger.info(body)
        logger.info("=" * 60)
        return True

    # Production mode: send via SMTP
    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_password = os.environ.get('SMTP_PASSWORD', '')
        smtp_from = os.environ.get('SMTP_FROM', smtp_user)
        smtp_tls = os.environ.get('SMTP_TLS', 'true').lower() == 'true'

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = to

        msg.attach(MIMEText(body, 'plain'))
        if html:
            msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, to, msg.as_string())

        logger.info(f"Email sent to {to}: {subject}")
        return True

    except (smtplib.SMTPException, socket.error, OSError) as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def send_password_reset_email(user, token: str) -> bool:
    """
    Send password reset email to user.

    Args:
        user: User model instance
        token: Password reset token

    Returns:
        True if email was sent successfully, False otherwise
    """
    # Generate reset URL
    # In development, use localhost; in production, use configured domain
    with current_app.app_context():
        reset_url = url_for('auth.reset_password', token=token, _external=True)

    subject = f"Password Reset - {current_app.config.get('APP_NAME', 'Creator Hub')}"

    body = f"""Hi{' ' + user.name if user.name else ''},

You requested a password reset for your account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.

Best regards,
{current_app.config.get('APP_NAME', 'Creator Hub')}
"""

    html = f"""
<p>Hi{' ' + user.name if user.name else ''},</p>

<p>You requested a password reset for your account.</p>

<p><a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 6px;">Reset Password</a></p>

<p>Or copy this link: <code>{reset_url}</code></p>

<p><small>This link will expire in 1 hour.</small></p>

<p>If you didn't request this, you can safely ignore this email.</p>

<p>Best regards,<br>{current_app.config.get('APP_NAME', 'Creator Hub')}</p>
"""

    return send_email(user.email, subject, body, html)


def send_email_verification(user, token: str) -> bool:
    """
    Send email verification email to user.

    Args:
        user: User model instance
        token: Email verification token

    Returns:
        True if email was sent successfully, False otherwise
    """
    with current_app.app_context():
        verify_url = url_for('auth.verify_email', token=token, _external=True)

    subject = f"Verify Your Email - {current_app.config.get('APP_NAME', 'Creator Hub')}"

    body = f"""Hi{' ' + user.name if user.name else ''},

Welcome! Please verify your email address to complete your registration.

Click the link below to verify your email:
{verify_url}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.

Best regards,
{current_app.config.get('APP_NAME', 'Creator Hub')}
"""

    html = f"""
<p>Hi{' ' + user.name if user.name else ''},</p>

<p>Welcome! Please verify your email address to complete your registration.</p>

<p><a href="{verify_url}" style="display: inline-block; padding: 12px 24px; background-color: #10B981; color: white; text-decoration: none; border-radius: 6px;">Verify Email</a></p>

<p>Or copy this link: <code>{verify_url}</code></p>

<p><small>This link will expire in 24 hours.</small></p>

<p>If you didn't create an account, you can safely ignore this email.</p>

<p>Best regards,<br>{current_app.config.get('APP_NAME', 'Creator Hub')}</p>
"""

    return send_email(user.email, subject, body, html)
