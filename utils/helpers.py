import os
import subprocess
import sys
from datetime import datetime

from config import REFERENCE_RANGES, LOGO_PATH

SEVERITY_ORDER = {"normal": 0, "info": 1, "warning": 2, "critical": 3}
TS_FMT = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    return datetime.now().strftime(TS_FMT)


def ts_str(dt: datetime) -> str:
    return dt.strftime(TS_FMT)


def param_status(param: str, value: float, ranges: dict | None = None) -> str:
    """Return 'normal' | 'warning' | 'critical' for a reading."""
    lo_w, lo_n, hi_n, hi_w = (ranges or REFERENCE_RANGES)[param]["range"]
    if value < lo_w or value > hi_w:
        return "critical"
    if value < lo_n or value > hi_n:
        return "warning"
    return "normal"


def overall_status(reading: dict, ranges: dict | None = None) -> str:
    worst = "normal"
    for p in (ranges or REFERENCE_RANGES):
        if p in reading and reading[p] is not None:
            s = param_status(p, reading[p], ranges)
            if SEVERITY_ORDER[s] > SEVERITY_ORDER[worst]:
                worst = s
    return worst


def format_duration(td) -> str:
    total = max(int(td.total_seconds()), 0)
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    return f"{d}d {h:02d}h {m:02d}m"


def ensure_logo():
    """Generate the ASTRA-MED logo with Pillow on first run (no binary assets shipped)."""
    if LOGO_PATH.exists():
        return LOGO_PATH
    from PIL import Image, ImageDraw
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((16, 16, S - 16, S - 16), fill="#0E1626", outline="#38BDF8", width=14)
    d.ellipse((90, 170, S - 90, S - 170), outline="#8B5CF6", width=10)
    pts = [(256, 110), (290, 226), (402, 226), (312, 296), (346, 410), (256, 342),
           (166, 410), (200, 296), (110, 226), (222, 226)]
    d.polygon(pts, fill="#F8FAFC")
    img.save(LOGO_PATH)
    return LOGO_PATH


def open_path(path):
    """Open a file/folder with the OS default application."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
