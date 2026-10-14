CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT UNIQUE NOT NULL,
    weight REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,          -- concert | cultural | trip | other
    city TEXT,
    country TEXT,
    venue TEXT,
    date_options TEXT,               -- JSON array de datas possiveis ["2026-03-01", ...]
    chosen_date TEXT,                -- YYYY-MM-DD definida ao aceitar
    tags TEXT,                       -- JSON array ["rock","museu","praia",...]
    source_url TEXT,
    price TEXT,
    notes TEXT,
    score REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | accepted | rejected | attended
    created_at TEXT NOT NULL,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    period_days INTEGER NOT NULL,
    min_count INTEGER NOT NULL DEFAULT 1,
    window_type TEXT NOT NULL DEFAULT 'rolling',
    weekend_only INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
