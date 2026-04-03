CREATE TABLE IF NOT EXISTS mom (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    baby_name TEXT DEFAULT '',
    due_date TEXT NOT NULL,
    baby_gender TEXT DEFAULT 'unknown',
    timezone TEXT DEFAULT 'America/New_York',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mom_id TEXT NOT NULL REFERENCES mom(id),
    role TEXT NOT NULL CHECK(role IN ('baby', 'mom')),
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'chat' CHECK(message_type IN (
        'chat', 'checkin_morning', 'checkin_afternoon', 'checkin_evening',
        'surprise', 'mood_ask', 'milestone'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mood_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mom_id TEXT NOT NULL REFERENCES mom(id),
    mood TEXT NOT NULL,
    mood_score REAL NOT NULL,
    notes TEXT DEFAULT '',
    source TEXT DEFAULT 'checkin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mom_id TEXT NOT NULL REFERENCES mom(id),
    scheduled_for TIMESTAMP NOT NULL,
    message_type TEXT NOT NULL,
    delivered INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_mom ON messages(mom_id, created_at);
CREATE INDEX IF NOT EXISTS idx_mood_mom ON mood_log(mom_id, created_at);
CREATE INDEX IF NOT EXISTS idx_scheduled ON scheduled_messages(delivered, scheduled_for);
