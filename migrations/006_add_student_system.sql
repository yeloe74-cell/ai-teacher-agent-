-- 006_add_student_system.sql
-- Part 7: Student Project System

CREATE TABLE IF NOT EXISTS project_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    deadline TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    month TEXT NOT NULL,
    challenge_id INTEGER,
    project_repo TEXT,
    video_link TEXT,
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    review_status TEXT DEFAULT 'pending',
    feedback TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    FOREIGN KEY (challenge_id) REFERENCES project_challenges(id)
);
