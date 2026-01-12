"""Database migration script for V2"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def migrate():
    """Run database migrations"""
    logger.info("Starting database migration")
    
    try:
        async with engine.begin() as conn:
            # Check if columns exist
            result = await conn.execute(
                "PRAGMA table_info(dialog_history)"
            )
            columns = [row[1] for row in result.fetchall()]
            
            # Add memory_type if missing
            if "memory_type" not in columns:
                logger.info("Adding memory_type column")
                await conn.execute(
                    "ALTER TABLE dialog_history ADD COLUMN memory_type VARCHAR(50)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dialog_history_memory_type "
                    "ON dialog_history(memory_type)"
                )
            
            # Add importance if missing
            if "importance" not in columns:
                logger.info("Adding importance column")
                await conn.execute(
                    "ALTER TABLE dialog_history ADD COLUMN importance VARCHAR(20)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dialog_history_importance "
                    "ON dialog_history(importance)"
                )
            
            # Add expires_at if missing
            if "expires_at" not in columns:
                logger.info("Adding expires_at column")
                await conn.execute(
                    "ALTER TABLE dialog_history ADD COLUMN expires_at DATETIME"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dialog_history_expires_at "
                    "ON dialog_history(expires_at)"
                )
            
            # Update existing rows
            logger.info("Updating existing rows with defaults")
            await conn.execute(
                "UPDATE dialog_history SET memory_type = 'conversation' "
                "WHERE memory_type IS NULL"
            )
            await conn.execute(
                "UPDATE dialog_history SET importance = 'low' "
                "WHERE importance IS NULL"
            )
            
            await conn.commit()
        
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error("Migration failed", error=str(e))
        return False


if __name__ == "__main__":
    success = asyncio.run(migrate())
    sys.exit(0 if success else 1)
