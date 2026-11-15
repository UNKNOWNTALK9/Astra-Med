import os
import queue
import threading
from datetime import datetime, timedelta
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog

from config import COLORS, EXPORT_DIR
from components.cards import Card, danger_button, font, ghost_button, labeled_combo, labeled_entry, primary_button
from components.dialogs import confirm, error, info
from components.table import DataTable
from database.database import Database
from modules.base_page import BasePage
from services import export_service
from services.pdf_service import build_report
from utils.helpers import open_path
from utils.validators import ValidationError, validate_date


class ReportsPage(BasePage):
    title = "Medical Reports"
    subtitle = "Generate PDF reports and export CSV / Excel health records"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.q = queue.Queue()
        box = Card(self.body)
        box.pack(fill="x")
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        f, self.astro_cb = labeled_combo(row, "Astronaut", [f'{a["id"]} {a["name"]}' for a in app.astronauts], 220); f.pack(side="left", padx=4)
        f, self.from_e = labeled_entry(row, "From (YYYY-MM-DD)", 110, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")); f.pack(side="left", padx=4)
        f, self.to_e = labeled_entry(row, "To (YYYY-MM-DD)", 110, datetime.now().strftime("%Y-%m-%d")); f.pack(side="left", padx=4)
        opts = ctk.CTkFrame(row, fg_color="transparent")
        opts.pack(side="left", padx=12)
        self.chk = {}
        for k, t, on in (("charts", "Charts", 1), ("anomalies", "AI anomalies", 1), ("alerts", "Alert history", 1), ("history", "Medical history", 0)):
            cb = ctk.CTkCheckBox(opts, text=t, font=font(11), width=20)
            if on:
                cb.select()
            if k == "history" and not self.can("medical_history"):
                cb.configure(state="disabled", text="Medical history (restricted)")
            cb.pack(anchor="w")
            self.chk[k] = cb
        btns = ctk.CTkFrame(box, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 12))
        self.pdf_btn = primary_button(btns, "Generate PDF report", self.make_pdf, 170)
        self.pdf_btn.pack(side="left", padx=4)
        ghost_button(btns, "Export CSV", lambda: self.export("csv"), 110).pack(side="left", padx=4)
        ghost_button(btns, "Export Excel", lambda: self.export("xlsx"), 110).pack(side="left", padx=4)
        self.status = ctk.CTkLabel(btns, text="", text_color=COLORS["text_dim"], font=font(11))
        self.status.pack(side="left", padx=12)

        ctk.CTkLabel(self.body, text="GENERATED REPORTS", text_color=COLORS["text_dim"], font=font(10, "bold")).pack(anchor="w", pady=(14, 4))
        self.table = DataTable(self.body, [("created_at", "Created", 130), ("title", "Title", 230), ("full_name", "Astronaut", 150),
                                           ("period", "Period", 170), ("username", "By", 80), ("file_path", "File", 300)], height=10, selectmode="browse")
        self.table.pack(fill="both", expand=True)
        row2 = ctk.CTkFrame(self.body, fg_color="transparent")
        row2.pack(fill="x", pady=6)
        ghost_button(row2, "Open", self.open, 90).pack(side="left", padx=3)
        ghost_button(row2, "Open folder", lambda: open_path(EXPORT_DIR), 110).pack(side="left", padx=3)
        danger_button(row2, "Delete", self.delete, 90).pack(side="left", padx=3)
        self.refresh()
        self.after(500, self._poll)

    def refresh(self):
        rows = self.app.db.list_reports()
        for r in rows:
            r["period"] = f'{r["date_from"]} → {r["date_to"]}'
            r["full_name"] = r["full_name"] or "(deleted)"
        self.table.set_rows(rows)

    def _params(self):
        code = self.astro_cb.get().split()[0]
        a = next(x for x in self.app.astronauts if x["id"] == code)
        start = datetime.strptime(validate_date(self.from_e.get(), "From"), "%Y-%m-%d")
        end = datetime.strptime(validate_date(self.to_e.get(), "To"), "%Y-%m-%d") + timedelta(days=1)
        return a, start, end

    def make_pdf(self):
        try:
            a, start, end = self._params()
        except ValidationError as e:
            return error(self, "Report", str(e))
        opts = {k: bool(c.get()) for k, c in self.chk.items()}
        self.pdf_btn.configure(state="disabled", text="Generating…")
        self.status.configure(text="Rendering charts and PDF in the background…")
        path, user, det = self.app.db.path, self.app.user, self.app.detector

        def work():
            try:
                db = Database(path)
                out = build_report(db, user, a["db_id"], start, end, None, det, opts["charts"], opts["anomalies"],
                                   opts["alerts"], opts["history"])
                db.close()
                self.q.put(("ok", out))
            except Exception as e:
                self.q.put(("err", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                self.pdf_btn.configure(state="normal", text="Generate PDF report")
                self.status.configure(text="")
                if kind == "ok":
                    self.refresh()
                    if confirm(self, "Report ready", f"Saved to\n{payload}\n\nOpen it now?"):
                        open_path(payload)
                else:
                    error(self, "Report failed", payload)
        except queue.Empty:
            pass
        self.after(500, self._poll)

    def export(self, kind):
        try:
            a, start, end = self._params()
        except ValidationError as e:
            return error(self, "Export", str(e))
        db = self.app.db
        df = export_service.readings_for_export(db, a["db_id"], start, end)
        if df.empty:
            return info(self, "Export", "No readings in this period.")
        path = filedialog.asksaveasfilename(defaultextension=f".{kind}", initialdir=str(EXPORT_DIR),
                                            initialfile=f'{a["id"]}_health_{datetime.now():%Y%m%d}.{kind}')
        if not path:
            return
        if kind == "csv":
            export_service.export_csv(df, path)
        else:
            from core import analytics_engine as ae
            alerts = db.list_alerts(astronaut_id=a["db_id"], limit=5000, start=start, end=end)
            import pandas as pd
            export_service.export_excel(path, {
                "Summary": ae.summary_stats(db.readings_df([a["db_id"]], start, end)).drop(columns=["param"]),
                "Readings": df,
                "Alerts": pd.DataFrame(alerts)[["timestamp", "severity", "parameter", "value", "message", "acknowledged"]] if alerts else pd.DataFrame({"info": ["no alerts"]})})
        db.add_report(a["db_id"], f'{a["name"]} {kind.upper()} export', path, kind, self.from_e.get(), self.to_e.get(), self.app.user["id"])
        db.log("INFO", "reports", f"{kind.upper()} exported for {a['id']}", self.app.user["id"])
        self.refresh()
        info(self, "Export complete", f"Saved to\n{path}")

    def _sel(self):
        r = self.table.selected()
        if not r:
            info(self, "Reports", "Select a report first.")
        return r

    def open(self):
        r = self._sel()
        if r:
            if Path(r["file_path"]).exists():
                open_path(r["file_path"])
            else:
                error(self, "Missing file", "The file no longer exists on disk.")

    def delete(self):
        r = self._sel()
        if r and confirm(self, "Delete report", "Delete this report record and its file?"):
            try:
                Path(r["file_path"]).unlink(missing_ok=True)
            except OSError:
                pass
            self.app.db.delete_report(r["id"])
            self.refresh()

    def on_show(self):
        self.refresh()
