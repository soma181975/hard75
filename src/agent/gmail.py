"""Gmail API client for fetching and processing emails."""

import base64
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


@dataclass
class EmailMessage:
    """Parsed email message."""

    id: str  # Gmail internal ID
    thread_id: str
    message_id: str  # RFC Message-ID header (e.g., <abc123@mail.gmail.com>)
    sender: str
    subject: str
    date: str
    body_text: str
    body_html: str
    attachments: list[dict]


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(self):
        self._service = None
        self._settings = get_settings()

    def _get_credentials(self) -> Credentials:
        """Get or refresh credentials."""
        creds = None
        token_path = Path(self._settings.gmail_token_file)
        creds_path = Path(self._settings.gmail_credentials_file)

        if token_path.exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {creds_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        return creds

    @property
    def service(self):
        """Get Gmail service instance."""
        if not self._service:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def get_unread_messages(self, max_results: int = 10) -> list[EmailMessage]:
        """Fetch unread messages from inbox."""
        results = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=max_results,
            )
            .execute()
        )

        messages = results.get("messages", [])
        parsed = []

        for msg in messages:
            full_msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )
            parsed.append(self._parse_message(full_msg))

        return parsed

    def _parse_message(self, msg: dict) -> EmailMessage:
        """Parse a Gmail message into our format."""
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

        # Extract body
        body_text = ""
        body_html = ""
        attachments = []

        def process_parts(parts):
            nonlocal body_text, body_html, attachments
            for part in parts:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body_text = base64.urlsafe_b64decode(data).decode("utf-8")
                elif mime_type == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body_html = base64.urlsafe_b64decode(data).decode("utf-8")
                elif part.get("filename"):
                    attachments.append(
                        {
                            "filename": part["filename"],
                            "mime_type": mime_type,
                            "attachment_id": part["body"].get("attachmentId"),
                            "size": part["body"].get("size", 0),
                        }
                    )
                elif "parts" in part:
                    process_parts(part["parts"])

        payload = msg["payload"]
        if "parts" in payload:
            process_parts(payload["parts"])
        else:
            # Single part message
            mime_type = payload.get("mimeType", "")
            data = payload.get("body", {}).get("data", "")
            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                if mime_type == "text/html":
                    body_html = decoded
                else:
                    body_text = decoded

        return EmailMessage(
            id=msg["id"],
            thread_id=msg["threadId"],
            message_id=headers.get("message-id", ""),
            sender=headers.get("from", ""),
            subject=headers.get("subject", ""),
            date=headers.get("date", ""),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download an attachment."""
        attachment = (
            self.service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return base64.urlsafe_b64decode(attachment["data"])

    def mark_as_read(self, message_id: str) -> None:
        """Mark a message as read."""
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    def send_reply(
        self,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
    ) -> None:
        """Send a reply email."""
        import email.mime.text
        import email.utils

        message = email.mime.text.MIMEText(body)
        message["to"] = to
        message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject

        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        self.service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()


# Global client instance
gmail_client = GmailClient()
