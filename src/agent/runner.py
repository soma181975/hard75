"""Main polling loop for processing emails."""

import asyncio
import logging
import re
from datetime import datetime

from src.config import get_settings
from src.db import db
from src.storage import storage
from src.agent.gmail import gmail_client, EmailMessage
from src.agent.extractor import extractor
from src.agent.merger import merger

logger = logging.getLogger(__name__)


def extract_email_address(sender: str) -> str:
    """Extract email address from sender string like 'Name <email@example.com>'."""
    match = re.search(r"<(.+?)>", sender)
    if match:
        return match.group(1).lower()
    return sender.lower().strip()


class AgentRunner:
    """Main agent that polls for emails and processes them."""

    def __init__(self):
        self._settings = get_settings()
        self._running = False

    async def run(self) -> None:
        """Start the polling loop."""
        self._running = True
        logger.info("Agent runner starting...")

        while self._running:
            try:
                await self._process_emails()
            except Exception as e:
                logger.exception(f"Error in agent loop: {e}")

            # Wait for next poll
            await asyncio.sleep(self._settings.agent_poll_interval_seconds)

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False

    async def _process_emails(self) -> None:
        """Process unread emails."""
        logger.info("Checking for new emails...")

        try:
            messages = gmail_client.get_unread_messages(max_results=10)
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            return

        for msg in messages:
            await self._process_message(msg)

    async def _process_message(self, msg: EmailMessage) -> None:
        """Process a single email message."""
        # Check if already processed
        existing = await db.fetchrow(
            "SELECT id FROM processed_emails WHERE message_id = $1",
            msg.id,
        )
        if existing:
            logger.debug(f"Message {msg.id} already processed, skipping")
            return

        logger.info(f"Processing message from {msg.sender}: {msg.subject}")

        sender_email = extract_email_address(msg.sender)

        # Look up sender
        user = await db.fetchrow(
            "SELECT * FROM users WHERE LOWER(email) = $1",
            sender_email,
        )

        if not user:
            # Check if this is a pending sender
            pending = await db.fetchrow(
                "SELECT * FROM pending_senders WHERE LOWER(email) = $1",
                sender_email,
            )

            if pending:
                if pending["status"] == "approved" and pending["approved_user_id"]:
                    # User was approved, fetch their record
                    user = await db.fetchrow(
                        "SELECT * FROM users WHERE id = $1",
                        pending["approved_user_id"],
                    )
                else:
                    # Update message count
                    await db.execute(
                        """
                        UPDATE pending_senders
                        SET message_count = message_count + 1,
                            last_message_at = NOW()
                        WHERE id = $1
                        """,
                        pending["id"],
                    )
                    await self._record_processed(msg.id, None, "skipped", "Pending approval")
                    gmail_client.mark_as_read(msg.id)
                    return
            else:
                # New unknown sender - add to pending
                await db.execute(
                    """
                    INSERT INTO pending_senders (email)
                    VALUES ($1)
                    ON CONFLICT (email) DO UPDATE
                    SET message_count = pending_senders.message_count + 1,
                        last_message_at = NOW()
                    """,
                    sender_email,
                )
                logger.info(f"New pending sender: {sender_email}")
                await self._record_processed(msg.id, None, "skipped", "Unknown sender")
                gmail_client.mark_as_read(msg.id)
                return

        if not user:
            await self._record_processed(msg.id, None, "skipped", "No user found")
            gmail_client.mark_as_read(msg.id)
            return

        # Process attachments (photos)
        photo_urls = []
        images = []

        for attachment in msg.attachments:
            if attachment["mime_type"].startswith("image/"):
                try:
                    img_data = gmail_client.get_attachment(msg.id, attachment["attachment_id"])

                    # Upload to storage
                    url = storage.upload_bytes(
                        img_data,
                        attachment["filename"],
                        attachment["mime_type"],
                        folder=f"photos/{user['id']}",
                    )
                    photo_urls.append(url)

                    # Add to images for extraction
                    images.append((img_data, attachment["mime_type"]))
                except Exception as e:
                    logger.error(f"Failed to process attachment: {e}")

        # Extract data using Claude
        try:
            extraction = extractor.extract_from_email(
                body_text=msg.body_text,
                body_html=msg.body_html,
                images=images[:3],  # Limit to 3 images for API
            )
        except Exception as e:
            logger.error(f"Failed to extract data: {e}")
            await self._record_processed(msg.id, user["id"], "failed", str(e))
            gmail_client.mark_as_read(msg.id)
            return

        # Merge into database
        try:
            results = await merger.merge(
                user_id=user["id"],
                extraction=extraction,
                photo_urls=photo_urls,
            )
            logger.info(f"Merge results for user {user['id']}: {results}")
        except Exception as e:
            logger.error(f"Failed to merge data: {e}")
            await self._record_processed(msg.id, user["id"], "failed", str(e))
            gmail_client.mark_as_read(msg.id)
            return

        # Record success
        await self._record_processed(msg.id, user["id"], "success", None)
        gmail_client.mark_as_read(msg.id)
        logger.info(f"Successfully processed message {msg.id}")

    async def _record_processed(
        self,
        message_id: str,
        user_id: int | None,
        status: str,
        error_message: str | None,
    ) -> None:
        """Record that a message was processed."""
        await db.execute(
            """
            INSERT INTO processed_emails (message_id, user_id, status, error_message)
            VALUES ($1, $2, $3, $4)
            """,
            message_id,
            user_id,
            status,
            error_message,
        )


# Global runner instance
agent_runner = AgentRunner()


async def run_agent() -> None:
    """Entry point for running the agent."""
    # Connect to database
    await db.connect()

    try:
        await agent_runner.run()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_agent())
