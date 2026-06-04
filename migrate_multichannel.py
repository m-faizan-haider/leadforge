"""
Migration script to add multi-channel outreach columns to the leads table
and create the outreach_logs table.

Run this once after updating database/models.py:
    python migrate_multichannel.py

This is safe to run multiple times — it checks if columns/tables exist first.
"""

import sys
from sqlalchemy import text, inspect
from database.db import engine, init_db
from loguru import logger


def migrate():
    """Add multi-channel columns and outreach_logs table."""
    inspector = inspect(engine)

    with engine.begin() as conn:
        # ── Add new columns to leads table ──
        existing_columns = [col["name"] for col in inspector.get_columns("leads")]

        new_columns = {
            "linkedin_connection_note": "VARCHAR",
            "linkedin_followup": "VARCHAR",
            "whatsapp_message": "VARCHAR",
            "sms_message": "VARCHAR",
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                logger.info(f"Adding column leads.{col_name} ({col_type})")
                conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}"))
            else:
                logger.info(f"Column leads.{col_name} already exists — skipping")

        # ── Create outreach_logs table if not exists ──
        existing_tables = inspector.get_table_names()

        if "outreach_logs" not in existing_tables:
            logger.info("Creating outreach_logs table...")
            conn.execute(text("""
                CREATE TABLE outreach_logs (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER REFERENCES leads(id),
                    campaign_id INTEGER REFERENCES campaigns(id),
                    channel VARCHAR,
                    message_text TEXT,
                    status VARCHAR DEFAULT 'generated',
                    sent_at TIMESTAMP,
                    replied_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            # Add indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_outreach_logs_lead_id ON outreach_logs (lead_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_outreach_logs_campaign_id ON outreach_logs (campaign_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_outreach_logs_channel ON outreach_logs (channel)"))
            logger.info("outreach_logs table created successfully")
        else:
            logger.info("outreach_logs table already exists — skipping")

    logger.info("Multi-channel migration complete! ✅")


if __name__ == "__main__":
    logger.info("Running multi-channel outreach migration...")
    try:
        migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
