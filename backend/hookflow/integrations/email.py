"""Email destination integration - sends webhooks via email."""

import os
from datetime import datetime
from typing import Any
from jinja2 import Template

from hookflow.models.app import Webhook, Destination


class EmailDestination:
    """Delivers webhooks via email."""

    def __init__(self, destination: Destination):
        self.destination = destination
        self.config = destination.config or {}

    async def deliver(self, webhook: Webhook, app_name: str) -> dict[str, Any]:
        """
        Deliver webhook payload via email.
        
        Supports SendGrid, SES, and SMTP providers.
        """
        provider = self.config.get("provider", "smtp")
        to_emails = self.config.get("to", [])
        subject = self.config.get("subject") or f"New webhook from {app_name}"

        if not to_emails:
            raise ValueError("No recipient emails configured")

        # Render HTML body
        html_body = self._render_email_body(webhook, app_name)

        # Send based on provider
        if provider == "sendgrid":
            result = await self._send_sendgrid(to_emails, subject, html_body)
        elif provider == "ses":
            result = await self._send_ses(to_emails, subject, html_body)
        else:  # smtp
            result = await self._send_smtp(to_emails, subject, html_body)

        return result

    def _render_email_body(self, webhook: Webhook, app_name: str) -> str:
        """Render the HTML email body."""
        template_str = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <h2 style="color: #333;">New Webhook Received</h2>
  <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
    <tr>
      <td style="padding: 8px; border: 1px solid #ddd;"><strong>App:</strong></td>
      <td style="padding: 8px; border: 1px solid #ddd;">{{ app_name }}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border: 1px solid #ddd;"><strong>Webhook ID:</strong></td>
      <td style="padding: 8px; border: 1px solid #ddd; font-family: monospace;">{{ webhook_id }}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td>
      <td style="padding: 8px; border: 1px solid #ddd;">{{ created_at }}</td>
    </tr>
    {% if webhook.source_ip %}
    <tr>
      <td style="padding: 8px; border: 1px solid #ddd;"><strong>Source IP:</strong></td>
      <td style="padding: 8px; border: 1px solid #ddd;">{{ source_ip }}</td>
    </tr>
    {% endif %}
  </table>
  
  <h3 style="color: #333;">Payload:</h3>
  <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto;">{{ body_json }}</pre>
</body>
</html>
"""
        template = Template(template_str)
        return template.render(
            app_name=app_name,
            webhook_id=str(webhook.id),
            created_at=webhook.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if webhook.created_at else "N/A",
            source_ip=webhook.source_ip,
            body_json=webhook.body or {},
        )

    async def _send_sendgrid(self, to_emails: list[str], subject: str, html_body: str) -> dict[str, Any]:
        """Send email via SendGrid."""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
            
            from_email = Email(self.config.get("from") or "noreply@hookflow.dev")
            to_list = [To(email) for email in to_emails]
            
            mail = Mail(from_email, to_list, subject, Content("text/html", html_body))
            
            response = sg.send(mail)
            
            return {
                "provider": "sendgrid",
                "status_code": response.status_code,
                "message": "Email sent successfully" if response.status_code in (200, 202) else "Failed",
            }
        except ImportError:
            raise ValueError("SendGrid package not installed. Run: pip install sendgrid")
        except Exception as e:
            raise RuntimeError(f"SendGrid error: {e}")

    async def _send_ses(self, to_emails: list[str], subject: str, html_body: str) -> dict[str, Any]:
        """Send email via AWS SES."""
        try:
            import boto3

            client = boto3.client(
                "ses",
                region_name=self.config.get("region", "us-east-1"),
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            )
            
            response = client.send_email(
                Source=self.config.get("from") or "noreply@hookflow.dev",
                Destination={"ToAddresses": to_emails},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": html_body}},
                },
            )
            
            return {
                "provider": "ses",
                "message_id": response.get("MessageId"),
                "status": "sent",
            }
        except ImportError:
            raise ValueError("boto3 package not installed. Run: pip install boto3")
        except Exception as e:
            raise RuntimeError(f"AWS SES error: {e}")

    async def _send_smtp(self, to_emails: list[str], subject: str, html_body: str) -> dict[str, Any]:
        """Send email via SMTP."""
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.config.get("from") or os.environ.get("SMTP_FROM", "noreply@hookflow.dev")
        msg["To"] = ", ".join(to_emails)
        msg.set_content(html_body, subtype="html")

        smtp_host = self.config.get("host") or os.environ.get("SMTP_HOST", "localhost")
        smtp_port = self.config.get("port") or int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = self.config.get("user") or os.environ.get("SMTP_USER")
        smtp_password = self.config.get("password") or os.environ.get("SMTP_PASSWORD")

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user and smtp_password:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                
                server.send_message(msg)
            
            return {
                "provider": "smtp",
                "status": "sent",
                "recipients": len(to_emails),
            }
        except Exception as e:
            raise RuntimeError(f"SMTP error: {e}")


async def deliver_email(
    webhook: Webhook,
    destination: Destination,
    app_name: str,
) -> dict[str, Any]:
    """
    Deliver a webhook via email.
    
    Args:
        webhook: The webhook to deliver
        destination: The email destination configuration
        app_name: The name of the app (for email subject)
        
    Returns:
        Delivery result with provider status
    """
    client = EmailDestination(destination)
    return await client.deliver(webhook, app_name)
