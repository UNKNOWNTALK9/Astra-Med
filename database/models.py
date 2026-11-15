"""SQLite schema (10 tables) with keys, constraints, and indexes."""
from config import PARAM_KEYS

_READING_COLS = ",\n    ".join(f"{p} REAL" for p in PARAM_KEYS)

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','medical_officer')),
    full_name TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_login TEXT
);
CREATE TABLE IF NOT EXISTS astronauts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    spacecraft TEXT NOT NULL DEFAULT '',
    blood_group TEXT NOT NULL DEFAULT '',
    emergency_contact_name TEXT NOT NULL DEFAULT '',
    emergency_contact_phone TEXT NOT NULL DEFAULT '',
    health_status TEXT NOT NULL DEFAULT 'normal' CHECK (health_status IN ('normal','warning','critical')),
    joined_date TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    spacecraft TEXT NOT NULL DEFAULT '',
    launch_date TEXT NOT NULL,
    return_date TEXT NOT NULL,
    duration_days INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned','Active','Completed','Aborted')),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS mission_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    astronaut_id INTEGER NOT NULL REFERENCES astronauts(id) ON DELETE CASCADE,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (mission_id, astronaut_id)
);
CREATE TABLE IF NOT EXISTS health_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id INTEGER NOT NULL REFERENCES astronauts(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    {_READING_COLS},
    status TEXT NOT NULL DEFAULT 'normal',
    is_simulated INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id INTEGER NOT NULL REFERENCES astronauts(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('normal','info','warning','critical')),
    parameter TEXT NOT NULL DEFAULT '',
    value REAL,
    message TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'threshold',
    acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    acknowledged_at TEXT
);
CREATE TABLE IF NOT EXISTS medical_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id INTEGER NOT NULL REFERENCES astronauts(id) ON DELETE CASCADE,
    entry_date TEXT NOT NULL,
    condition TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    recorded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS health_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id INTEGER REFERENCES astronauts(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'pdf',
    date_from TEXT,
    date_to TEXT,
    generated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    level TEXT NOT NULL DEFAULT 'INFO',
    source TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    user_id INTEGER
);
CREATE TABLE IF NOT EXISTS application_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_readings_astro_ts ON health_readings(astronaut_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON health_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_readings_status ON health_readings(status);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_sev_ack ON alerts(severity, acknowledged);
CREATE INDEX IF NOT EXISTS idx_alerts_astro ON alerts(astronaut_id);
CREATE INDEX IF NOT EXISTS idx_assign_mission ON mission_assignments(mission_id);
CREATE INDEX IF NOT EXISTS idx_assign_astro ON mission_assignments(astronaut_id);
CREATE INDEX IF NOT EXISTS idx_history_astro ON medical_history(astronaut_id);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON system_logs(timestamp);
"""

TABLES = ["users", "astronauts", "missions", "mission_assignments", "health_readings",
          "alerts", "medical_history", "health_reports", "system_logs", "application_settings"]
