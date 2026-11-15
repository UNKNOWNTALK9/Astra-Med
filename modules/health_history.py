from datetime import datetime, timedelta

import customtkinter as ctk

from config import COLORS, PARAM_KEYS, REFERENCE_RANGES
from components.cards import font, ghost_button, labeled_combo, labeled_entry, primary_button
from components.charts import ChartPanel
from components.dialogs import error, info
from components.table import DataTable
from modules.base_page import BasePage
from services import export_service
from utils.helpers import open_path
from utils.validators import ValidationError, validate_date
from config import EXPORT_DIR
from tkinter import filedialog

PAGE_SIZE = 50


class HealthHistoryPage(BasePage):
    title = "Health History"
    subtitle = "Stored readings (SQLite). Filter, compare, graph and export."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.page, self.total = 0, 0
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x")
        self.names = ["All astronauts"] + [f'{a["id"]} {a["name"]}' for a in app.astronauts]
        f, self.astro_cb = labeled_combo(bar, "Astronaut", self.names, 210); f.pack(side="left", padx=4)
        f, self.from_e = labeled_entry(bar, "From (YYYY-MM-DD)", 105, (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")); f.pack(side="left", padx=4)
        f, self.to_e = labeled_entry(bar, "To (YYYY-MM-DD)", 105, datetime.now().strftime("%Y-%m-%d")); f.pack(side="left", padx=4)
        f, self.param_cb = labeled_combo(bar, "Graph parameter", [REFERENCE_RANGES[p]["label"] for p in PARAM_KEYS], 130); f.pack(side="left", padx=4)
        self.abn = ctk.CTkCheckBox(bar, text="Abnormal only", font=font(11)); self.abn.pack(side="left", padx=10, pady=(16, 0))
        primary_button(bar, "Search", self.search, 90).pack(side="left", padx=4, pady=(16, 0))
        ghost_button(bar, "Export Excel", lambda: self.export("xlsx"), 100).pack(side="right", padx=3, pady=(16, 0))
        ghost_button(bar, "Export CSV", lambda: self.export("csv"), 100).pack(side="right", padx=3, pady=(16, 0))
        ghost_button(bar, "Compare ↔ previous", self.compare, 150).pack(side="right", padx=3, pady=(16, 0))

        cols = [("timestamp", "Time", 135), ("code", "ID", 65), ("heart_rate", "HR", 50), ("spo2", "SpO2", 50),
                ("bp", "BP", 70), ("temperature", "Temp", 55), ("resp_rate", "Resp", 50), ("activity", "Act", 50),
                ("sleep", "Sleep", 50), ("hydration", "Hydr", 50), ("stress", "Stress", 50), ("status", "Status", 70)]
        self.table = DataTable(self.body, cols, height=9, on_select=lambda r: self.graph_selected())
        self.table.pack(fill="x", pady=8)
        nav = ctk.CTkFrame(self.body, fg_color="transparent")
        nav.pack(fill="x")
        ghost_button(nav, "◀ Prev", lambda: self.go(-1), 80).pack(side="left")
        self.page_lbl = ctk.CTkLabel(nav, text="", text_color=COLORS["text_dim"], font=font(11))
        self.page_lbl.pack(side="left", padx=10)
        ghost_button(nav, "Next ▶", lambda: self.go(1), 80).pack(side="left")
        self.chart = ChartPanel(self.body)
        self.chart.pack(fill="both", expand=True, pady=(8, 0))
        self.search()

    def preselect(self, astronaut_code=None, **_):
        if astronaut_code:
            for n in self.names:
                if n.startswith(astronaut_code):
                    self.astro_cb.set(n)
            self.page = 0
            self.search()

    def _filters(self):
        sel = self.astro_cb.get()
        aid = None
        if sel != "All astronauts":
            aid = next((a["db_id"] for a in self.app.astronauts if a["id"] == sel.split()[0]), None)
        start = datetime.strptime(validate_date(self.from_e.get(), "From", True) or "1970-01-01", "%Y-%m-%d")
        end = datetime.strptime(validate_date(self.to_e.get(), "To", True) or "2999-01-01", "%Y-%m-%d") + timedelta(days=1)
        return aid, start, end, bool(self.abn.get())

    def search(self):
        self.page = 0
        self.load()

    def load(self):
        try:
            aid, start, end, abn = self._filters()
        except ValidationError as e:
            return error(self, "Filter", str(e))
        db = self.app.db
        self.total = db.count_readings(aid, start, end, abn)
        rows = db.query_readings(aid, start, end, abn, PAGE_SIZE, self.page * PAGE_SIZE)
        for r in rows:
            r["bp"] = f'{r["systolic"]:.0f}/{r["diastolic"]:.0f}'
        pages = max(1, -(-self.total // PAGE_SIZE))
        self.page_lbl.configure(text=f"Page {self.page + 1} / {pages}   ·   {self.total:,} readings")
        self.table.set_rows(rows, tag_key="status", fmt=lambda k, r: (f"{r[k]:.1f}" if isinstance(r.get(k), float) else r.get(k, "")))
        self._draw_graph(aid, start, end)

    def go(self, d):
        pages = max(1, -(-self.total // PAGE_SIZE))
        np_ = self.page + d
        if 0 <= np_ < pages:
            self.page = np_
            self.load()

    def graph_selected(self):
        pass

    def _draw_graph(self, aid, start, end):
        p = next(k for k in PARAM_KEYS if REFERENCE_RANGES[k]["label"] == self.param_cb.get())
        df = self.app.db.readings_df([aid] if aid else None, start, end)
        if df.empty:
            return self.chart.message("No data for this filter")
        wide = df.pivot_table(index="timestamp", columns="code", values=p)
        if len(wide) > 1500:
            wide = wide.resample("h").mean()
        meta = REFERENCE_RANGES[p]

        def f(fig):
            ax = fig.add_subplot(111)
            for c in wide.columns:
                ax.plot(wide.index, wide[c], lw=1.1, label=c)
            ax.axhspan(*meta["range"][1:3], color=COLORS["normal"], alpha=0.07, lw=0)
            ax.set_title(f'{meta["label"]} history ({meta["unit"]})', loc="left", fontsize=10, fontweight="bold")
            ax.legend(fontsize=7, frameon=False, ncol=5, loc="upper left")
            fig.autofmt_xdate()
        self.chart.draw(f)

    def compare(self):
        r = self.table.selected()
        if not r:
            return info(self, "Compare", "Select a reading in the table first.")
        prev = self.app.db.previous_reading(r["astronaut_id"], r["timestamp"])
        if not prev:
            return info(self, "Compare", "No earlier reading exists for this astronaut.")
        rows = []
        for p in PARAM_KEYS:
            d = r[p] - prev[p]
            meta = REFERENCE_RANGES[p]
            rows.append({"param": meta["label"], "now": f'{r[p]:.2f}', "prev": f'{prev[p]:.2f}', "delta": f"{d:+.2f}",
                         "pct": f"{d / prev[p] * 100:+.1f}%" if prev[p] else "-", "unit": meta["unit"]})
        dlg = ctk.CTkToplevel(self)
        dlg.title(f'Compare {r["code"]}: {r["timestamp"]} vs {prev["timestamp"]}')
        dlg.configure(fg_color=COLORS["card"])
        t = DataTable(dlg, [("param", "Parameter", 140), ("now", "Selected", 90), ("prev", "Previous", 90),
                            ("delta", "Change", 80), ("pct", "% change", 80), ("unit", "Unit", 70)], height=10)
        t.pack(padx=12, pady=12)
        t.set_rows(rows)

    def export(self, kind):
        try:
            aid, start, end, _ = self._filters()
        except ValidationError as e:
            return error(self, "Filter", str(e))
        sel = self.table.selected_rows()
        df = export_service.readings_for_export(self.app.db, aid, start, end)
        if sel:  # export only the highlighted rows if any
            keys = {(r["code"], r["timestamp"]) for r in sel}
            df = df[[(c, t.strftime("%Y-%m-%d %H:%M:%S")) in keys for c, t in zip(df["astronaut_code"], df["timestamp"])]]
        path = filedialog.asksaveasfilename(defaultextension=f".{kind}", initialdir=str(EXPORT_DIR),
                                            initialfile=f"health_records_{datetime.now():%Y%m%d_%H%M}.{kind}")
        if not path:
            return
        (export_service.export_csv(df, path) if kind == "csv" else export_service.export_excel(path, {"Readings": df}))
        self.app.db.log("INFO", "export", f"Exported {len(df)} readings to {path}", self.app.user["id"])
        info(self, "Export complete", f"{len(df):,} records exported to\n{path}")

    def on_show(self):
        pass
