"""CSV / Excel export and CSV import."""
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import PARAM_KEYS
from utils.helpers import overall_status, ts_str


def export_csv(df: pd.DataFrame, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return Path(path)


def export_excel(path, sheets: dict, title="ASTRA-MED export"):
    """sheets: {sheet_name: DataFrame}. Styled header, frozen panes, auto widths."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df = df.copy()
            for c in df.select_dtypes(include=["datetimetz"]).columns:
                df[c] = df[c].dt.tz_localize(None)
            df.to_excel(xw, sheet_name=name[:31], index=False)
            ws = xw.sheets[name[:31]]
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="0E1626")
                cell.alignment = Alignment(horizontal="center")
            ws.freeze_panes = "A2"
            for i, col in enumerate(df.columns, 1):
                width = max([len(str(col))] + [len(str(v)) for v in df[col].head(200)]) + 2
                ws.column_dimensions[get_column_letter(i)].width = min(width, 40)
        xw.book.properties.title = title
        xw.book.properties.creator = "ASTRA-MED"
    return Path(path)


def readings_for_export(db, astronaut_id=None, start=None, end=None):
    df = db.readings_df([astronaut_id] if astronaut_id else None, start, end)
    df = df.drop(columns=["id", "astronaut_id"]).rename(columns={"code": "astronaut_code", "name": "astronaut_name"})
    df["data_source"] = "SIMULATED"
    return df


def import_readings_csv(db, path):
    """Import readings. Required columns: astronaut_code, timestamp and the 10 vital columns.
    Returns (imported, errors[list[str]])."""
    df = pd.read_csv(path)
    required = ["astronaut_code", "timestamp"] + PARAM_KEYS
    missing = [c for c in required if c not in df.columns]
    if missing:
        return 0, [f"Missing columns: {', '.join(missing)}"]
    ids = {a["code"]: a["id"] for a in db.list_astronauts()}
    rows, errors = [], []
    for i, r in df.iterrows():
        try:
            if r["astronaut_code"] not in ids:
                raise ValueError(f"unknown astronaut {r['astronaut_code']}")
            ts = pd.to_datetime(r["timestamp"]).to_pydatetime()
            vals = {p: float(r[p]) for p in PARAM_KEYS}
            rows.append({"astronaut_id": ids[r["astronaut_code"]], "timestamp": ts_str(ts), **vals,
                         "status": overall_status(vals)})
        except Exception as e:
            errors.append(f"Row {i + 2}: {e}")
    db.insert_readings(rows)
    return len(rows), errors[:50]
