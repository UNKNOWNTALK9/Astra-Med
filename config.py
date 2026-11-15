import copy
from pathlib import Path

APP_NAME = "ASTRA-MED"
APP_FULL_NAME = "ASTRA-MED | Astronaut Health Monitoring & Mission Control System"
TAGLINE = "Monitoring Human Health Beyond Earth."
VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "astronaut.db"
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR = BASE_DIR / "models"
BACKUP_DIR = BASE_DIR / "backups"
EXPORT_DIR = BASE_DIR / "reports"
LOGO_PATH = BASE_DIR / "assets" / "images" / "logo.png"
for _d in (REPORTS_DIR, MODELS_DIR, BACKUP_DIR, LOGO_PATH.parent):
    _d.mkdir(parents=True, exist_ok=True)

COLORS = {
    "bg": "#080D18",
    "sidebar": "#0E1626",
    "card": "#151F32",
    "card_hover": "#1B2842",
    "border": "#223049",
    "primary": "#38BDF8",
    "secondary": "#8B5CF6",
    "normal": "#22C55E",
    "warning": "#F59E0B",
    "critical": "#EF4444",
    "text": "#F8FAFC",
    "text_dim": "#94A3B8",
}
STATUS_COLORS = {
    "normal": COLORS["normal"],
    "warning": COLORS["warning"],
    "critical": COLORS["critical"],
    "info": COLORS["primary"],
}
ASTRONAUT_COLORS = ["#38BDF8", "#8B5CF6", "#22C55E", "#F59E0B", "#F472B6", "#2DD4BF"]

FONT_FAMILY = "Segoe UI"

# (key, label, icon)
NAV_ITEMS = [
    ("dashboard", "Mission Overview", "◉"),
    ("monitoring", "Astronaut Monitoring", "♥"),
    ("analytics", "Vital Signs Analytics", "▤"),
    ("history", "Health History", "⟲"),
    ("ai", "AI Health Analysis", "✦"),
    ("alerts", "Alerts & Notifications", "▲"),
    ("profiles", "Astronaut Profiles", "☺"),
    ("missions", "Mission Management", "➤"),
    ("reports", "Medical Reports", "▣"),
    ("settings", "System Settings", "⚙"),
]

# Default reference ranges: (warn_low, normal_low, normal_high, warn_high)
# Outside normal but inside warn bounds -> warning; outside warn bounds -> critical.
# Values are illustrative defaults for SIMULATED data, configurable in Settings (Phase 2+).
REFERENCE_RANGES = {
    "heart_rate": {"label": "Heart Rate", "unit": "BPM", "range": (40, 55, 100, 130)},
    "spo2": {"label": "SpO2", "unit": "%", "range": (90, 95, 100, 101)},
    "systolic": {"label": "Systolic BP", "unit": "mmHg", "range": (80, 90, 130, 160)},
    "diastolic": {"label": "Diastolic BP", "unit": "mmHg", "range": (50, 60, 85, 100)},
    "temperature": {"label": "Body Temp", "unit": "°C", "range": (35.0, 36.1, 37.5, 38.5)},
    "resp_rate": {"label": "Resp. Rate", "unit": "br/min", "range": (8, 12, 20, 26)},
    "activity": {"label": "Activity", "unit": "score", "range": (0, 10, 100, 101)},
    "sleep": {"label": "Sleep", "unit": "h", "range": (3, 6, 10, 13)},
    "hydration": {"label": "Hydration", "unit": "%", "range": (40, 55, 100, 101)},
    "stress": {"label": "Stress", "unit": "score", "range": (-1, 0, 60, 80)},
}

MONITOR_INTERVAL_SEC = 1.0
SIMULATION_NOTICE = "SIMULATED DATA - NOT ACTUAL MEDICAL MEASUREMENTS"

PARAM_KEYS = list(REFERENCE_RANGES)
DEFAULT_RANGES = copy.deepcopy(REFERENCE_RANGES)

ROLES = ("admin", "medical_officer")
ROLE_LABELS = {"admin": "Administrator", "medical_officer": "Medical Officer"}
# Least-privilege matrix. Only medical officers may read/write clinical medical history.
PERMISSIONS = {
    "admin": {"manage_users", "manage_astronauts", "manage_missions", "edit_settings",
              "backup", "import_data", "view_health", "generate_reports", "ack_alerts",
              "edit_thresholds"},
    "medical_officer": {"view_health", "ack_alerts", "medical_history", "generate_reports",
                        "edit_thresholds"},
}
BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
MISSION_STATUSES = ["Planned", "Active", "Completed", "Aborted"]
ACCENT_PRESETS = {"Sky": "#38BDF8", "Violet": "#8B5CF6", "Emerald": "#22C55E", "Amber": "#F59E0B"}
