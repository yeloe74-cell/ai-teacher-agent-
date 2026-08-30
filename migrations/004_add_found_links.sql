-- 004_add_found_links.sql
-- Link Scanner Table
-- Stores public group links found in messages.

CREATE TABLE IF NOT EXISTS found_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT UNIQUE NOT NULL,
    source_group_id TEXT,
    status TEXT DEFAULT 'found',
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster link queries by status
CREATE INDEX IF NOT EXISTS idx_found_links_status ON found_links(status);

-- Index for faster link queries by source
CREATE INDEX IF NOT EXISTS idx_found_links_source ON found_links(source_group_id);
