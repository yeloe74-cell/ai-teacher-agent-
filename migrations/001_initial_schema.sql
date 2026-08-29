-- 001_initial_schema.sql
-- Initial database schema for AI Teacher Bot
-- Part 1-2 tables

CREATE TABLE IF NOT EXISTS curriculum (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL,
    description TEXT,
    total_days INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    month TEXT NOT NULL,
    day_number INTEGER NOT NULL,
    lesson_type TEXT NOT NULL,
    topic TEXT NOT NULL,
    content TEXT,
    status TEXT DEFAULT 'pending',
    telegram_message_id TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    UNIQUE(month, day_number, lesson_type)
);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    group_id TEXT UNIQUE NOT NULL,
    group_title TEXT,
    status TEXT DEFAULT 'pending',
    auto_share INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS published_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    channel_message_id TEXT NOT NULL,
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    command TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    month TEXT NOT NULL,
    project_repo TEXT,
    video_link TEXT,
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    review_status TEXT DEFAULT 'pending',
    feedback TEXT
);

CREATE INDEX IF NOT EXISTS idx_lessons_month ON lessons(month);
CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status);
CREATE INDEX IF NOT EXISTS idx_groups_status ON groups(status);
