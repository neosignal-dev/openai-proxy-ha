-- Migration: Add Memory V2 fields to dialog_history table
-- Date: 2024-12-19
-- Description: Adds memory_type, importance, and expires_at columns for efficient filtering

-- Check if columns already exist before adding
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we need to handle it in code

-- Add memory_type column
ALTER TABLE dialog_history ADD COLUMN memory_type VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_dialog_history_memory_type ON dialog_history(memory_type);

-- Add importance column  
ALTER TABLE dialog_history ADD COLUMN importance VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_dialog_history_importance ON dialog_history(importance);

-- Add expires_at column
ALTER TABLE dialog_history ADD COLUMN expires_at DATETIME;
CREATE INDEX IF NOT EXISTS idx_dialog_history_expires_at ON dialog_history(expires_at);

-- Update existing rows (set defaults)
UPDATE dialog_history 
SET memory_type = 'conversation' 
WHERE memory_type IS NULL;

UPDATE dialog_history
SET importance = 'low'
WHERE importance IS NULL;

-- Log migration
-- INSERT INTO migration_log (version, description, applied_at) 
-- VALUES ('v2_memory_fields', 'Add Memory V2 fields', datetime('now'));
