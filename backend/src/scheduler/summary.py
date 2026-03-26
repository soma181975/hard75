"""Daily summary email job."""

import asyncio
import logging
from datetime import date, timedelta

from src.config import get_settings
from src.db import db
from src.agent.gmail import gmail_client

logger = logging.getLogger(__name__)


async def build_summary_html(user: dict) -> str:
    """Build HTML summary for a user."""
    user_id = user["id"]

    # Get streak
    streak = await db.fetchval("SELECT calculate_streak($1)", user_id)

    # Get total completed
    total = await db.fetchval(
        "SELECT COUNT(*) FROM hard75_days WHERE user_id = $1 AND all_done = TRUE",
        user_id,
    )

    # Get yesterday's progress
    yesterday = date.today() - timedelta(days=1)
    day = await db.fetchrow(
        """
        SELECT * FROM hard75_days
        WHERE user_id = $1 AND date = $2
        """,
        user_id,
        yesterday,
    )

    # Build HTML
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #1a1a1a;">Hard 75 Daily Summary</h1>
        <p>Hi {user['name']},</p>

        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h2 style="margin-top: 0;">Your Progress</h2>
            <p><strong>Current Streak:</strong> {streak or 0} days</p>
            <p><strong>Days Completed:</strong> {total or 0}/75</p>
            <p><strong>Progress:</strong> {round((total or 0) / 75 * 100, 1)}%</p>
        </div>
    """

    if day:
        checks = []
        if day["workout1_done"]:
            checks.append("Workout 1")
        if day["workout2_done"]:
            checks.append("Workout 2")
        if day["diet_done"]:
            checks.append("Diet")
        if day["water_done"]:
            checks.append("Water")
        if day["reading_done"]:
            checks.append("Reading")
        if day["photo_done"]:
            checks.append("Photo")

        html += f"""
        <div style="background: {'#d1fae5' if day['all_done'] else '#fef3c7'}; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h2 style="margin-top: 0;">Yesterday (Day {day['day_number']})</h2>
            <p><strong>Status:</strong> {'All tasks completed!' if day['all_done'] else 'Some tasks remaining'}</p>
            <p><strong>Completed:</strong> {', '.join(checks) if checks else 'None'}</p>
            {f"<p><strong>Steps:</strong> {day['steps']:,}</p>" if day['steps'] else ""}
        </div>
        """
    else:
        html += """
        <div style="background: #fee2e2; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h2 style="margin-top: 0;">Yesterday</h2>
            <p>No progress logged for yesterday. Don't forget to email your updates!</p>
        </div>
        """

    html += """
        <p style="color: #6b7280; font-size: 14px;">
            Keep pushing! Reply to this email with your daily update to log your progress.
        </p>
    </body>
    </html>
    """

    return html


async def send_daily_summaries() -> None:
    """Send daily summary emails to all active users."""
    logger.info("Sending daily summary emails...")

    # Get all users with a start date (actively doing the challenge)
    users = await db.fetch(
        """
        SELECT * FROM users
        WHERE start_date IS NOT NULL
        AND role = 'user'
        """
    )

    for user in users:
        try:
            html = await build_summary_html(dict(user))

            # Send email
            gmail_client.send_reply(
                thread_id=None,  # New thread
                to=user["email"],
                subject="Your Hard 75 Daily Summary",
                body=html,
            )
            logger.info(f"Sent summary to {user['email']}")

        except Exception as e:
            logger.error(f"Failed to send summary to {user['email']}: {e}")


async def run_summary_job() -> None:
    """Entry point for the summary job."""
    await db.connect()
    try:
        await send_daily_summaries()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_summary_job())
