import queue
import threading
from datetime import datetime, timedelta

import customtkinter as ctk
import numpy as np

from config import COLORS, REFERENCE_RANGES
from components.cards import Card, danger_button, font, ghost_button, labeled_combo, primary_button
from components.charts import ChartPanel
from components.dialogs import error, info
from components.table import DataTable
from core.anomaly_detector import DISCLAIMER, AnomalyDetector, MODEL_PATH
from database.database import Database
from modules.base_page import BasePage

WINDOWS = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "All data": None}


class AIAnalysisPage(BasePage):
    title = "AI Health Analysis"
    subtitle = "Isolation Forest anomaly screening with explainable reasons"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.q = queue.Queue()
        ctk.CTkLabel(self.body, text="⚠ " + DISCLAIMER, text_color=COLORS["warning"], font=font(11, "bold"),
                     wraplength=1000, justify="left").pack(anchor="w", pady=(0, 6))
        top = Card(self.body)
        top.pack(fill="x")
        self.model_lbl = ctk.CTkLabel(top, text="", text_color=COLORS["text"], font=font(11), justify="left", anchor="w")
        self.model_lbl.pack(side="left", padx=16, pady=10)
        self.train_btn = primary_button(top, "Retrain model", self.retrain, 130)
        self.train_btn.pack(side="right", padx=12)
        self.live_lbl = ctk.CTkLabel(top, text="", text_color=COLORS["text_dim"], font=font(11))
        self.live_lbl.pack(side="right", padx=12)

        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x", pady=8)
        f, self.astro_cb = labeled_combo(bar, "Astronaut", [f'{a["id"]} {a["name"]}' for a in app.astronauts], 220); f.pack(side="left", padx=4)
        f, self.win_cb = labeled_combo(bar, "Analysis window", list(WINDOWS), 140); f.pack(side="left", padx=4)
        self.win_cb.set("Last 30 days")
        primary_button(bar, "Run analysis", self.analyze, 120).pack(side="left", padx=8, pady=(16, 0))

        split = ctk.CTkFrame(self.body, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.grid_columnconfigure(0, weight=3)
        split.grid_columnconfigure(1, weight=2)
        split.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(split, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.chart = ChartPanel(left, figsize=(6, 2.6))
        self.chart.pack(fill="both", expand=True)
        self.table = DataTable(left, [("time", "Time", 120), ("score", "Score", 55), ("reasons", "Explainable reasons", 420)], height=7)
        self.table.pack(fill="x", pady=(6, 0))
        self.summary = ctk.CTkTextbox(split, fg_color=COLORS["card"], text_color=COLORS["text"], font=font(11), wrap="word",
                                      border_width=1, border_color=COLORS["border"])
        self.summary.grid(row=0, column=1, sticky="nsew")
        self.summary.insert("1.0", "Choose an astronaut and press “Run analysis”.")
        self.summary.configure(state="disabled")
        self.update_status()
        self.after(400, self._poll)

    def update_status(self):
        d = self.app.detector
        if d.ready:
            m = d.meta
            self.model_lbl.configure(text=(
                f'Model: IsolationForest(200 trees)   trained {m["trained_at"]}   {m["n_rows"]:,} readings / {m["n_astronauts"]} astronauts\n'
                f'Held-out test (last 20% in time): {m["test_flag_rate"] * 100:.1f}% flagged  ·  contamination target {m["contamination"] * 100:.0f}%'))
        else:
            self.model_lbl.configure(text="Model not trained yet.")
        self.live_lbl.configure(text="Live scoring: " + ("ON" if self.app.setting("ai_live", "1") == "1" else "OFF (Settings → Monitoring)"))

    def retrain(self):
        self.train_btn.configure(state="disabled", text="Training…")
        path = self.app.db.path

        def work():
            try:
                db = Database(path)
                det = AnomalyDetector()
                det.fit(db.readings_df())
                det.save(MODEL_PATH)
                db.log("INFO", "ai", "Anomaly model retrained")
                db.close()
                self.q.put(("ok", det))
            except Exception as e:
                self.q.put(("err", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                self.train_btn.configure(state="normal", text="Retrain model")
                if kind == "ok":
                    self.app.detector = payload
                    self.update_status()
                    info(self, "Model", "Model retrained and saved.")
                else:
                    error(self, "Training failed", payload)
        except queue.Empty:
            pass
        self.after(400, self._poll)

    def analyze(self):
        d = self.app.detector
        if not d.ready:
            return error(self, "AI analysis", "Model not trained. Press “Retrain model” first.")
        code = self.astro_cb.get().split()[0]
        a = next(x for x in self.app.astronauts if x["id"] == code)
        days = WINDOWS[self.win_cb.get()]
        start = datetime.now() - timedelta(days=days) if days else None
        df = self.app.db.readings_df([a["db_id"]], start, None)
        if len(df) < 20:
            return error(self, "AI analysis", "Not enough readings in this window.")
        scored = d.score_df(df)
        trends = AnomalyDetector.trends(df)
        text = d.summarize(a["name"], scored, trends)
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")
        top = scored[scored["is_anomaly"]].sort_values("anomaly_score", ascending=False).head(25)
        self.table.set_rows([{"time": f'{r["timestamp"]:%m-%d %H:%M}', "score": f'{r["anomaly_score"]:.0f}',
                              "reasons": "; ".join(d.reasons(r, code))} for _, r in top.iterrows()])
        s = scored.set_index("timestamp")

        def f(fig):
            ax = fig.add_subplot(111)
            ax.plot(s.index, s["anomaly_score"], color=COLORS["primary"], lw=0.8)
            fl = s[s["is_anomaly"]]
            ax.scatter(fl.index, fl["anomaly_score"], color=COLORS["critical"], s=14, zorder=3, label="flagged")
            ax.set_ylim(0, 105)
            ax.set_title(f'Anomaly score (0-100) · {a["name"]}', loc="left", fontsize=10, fontweight="bold")
            ax.legend(fontsize=7, frameon=False, loc="upper left")
            fig.autofmt_xdate()
        self.chart.draw(f)
