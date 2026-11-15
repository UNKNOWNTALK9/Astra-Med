from collections import deque
from datetime import datetime

import customtkinter as ctk

from config import ASTRONAUT_COLORS, COLORS, REFERENCE_RANGES, STATUS_COLORS
from components.cards import AstronautCard, Card, StatCard, font
from components.charts import LiveBarChart, LiveChart
from core.nasa_reference import MERCURY_DATA, NASA_FINDINGS, SOURCES
from modules.base_page import BasePage
from utils.helpers import overall_status, format_duration


class DashboardPage(BasePage):
    title = "Mission Overview"
    subtitle = "Live crew health status (simulated telemetry)"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.astronauts = app.astronauts
        self.colors = {a["id"]: ASTRONAUT_COLORS[i % len(ASTRONAUT_COLORS)] for i, a in enumerate(self.astronauts)}
        self.status = {a["id"]: a.get("health_status", "normal") for a in self.astronauts}
        self.latest = {}

        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        kpi = ctk.CTkFrame(scroll, fg_color="transparent")
        kpi.grid(row=0, column=0, sticky="ew")
        self.kpis = {}
        specs = [("total", "Total Astronauts", COLORS["primary"], "☺"), ("healthy", "Healthy", COLORS["normal"], "✔"),
                 ("attention", "Need Attention", COLORS["warning"], "!"), ("critical", "Critical Alerts", COLORS["critical"], "▲"),
                 ("duration", "Mission Duration", COLORS["secondary"], "⏱"), ("system", "Monitoring", COLORS["normal"], "◉")]
        for i, (k, t, c, ic) in enumerate(specs):
            kpi.grid_columnconfigure(i, weight=1, uniform="k")
            card = StatCard(kpi, t, "--", c, ic)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0 if i == 5 else 6))
            self.kpis[k] = card

        ctk.CTkLabel(scroll, text="CREW STATUS", text_color=COLORS["text_dim"], font=font(10, "bold")
                     ).grid(row=1, column=0, sticky="w", pady=(18, 6))
        crew = ctk.CTkFrame(scroll, fg_color="transparent")
        crew.grid(row=2, column=0, sticky="ew")
        self.cards = {}
        cols = max(1, min(len(self.astronauts), 5))
        for i, a in enumerate(self.astronauts):
            crew.grid_columnconfigure(i % cols, weight=1, uniform="c")
            c = AstronautCard(crew, a, self.colors[a["id"]])
            c.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            c.update_reading_status(self.status[a["id"]])
            self.cards[a["id"]] = c

        ctk.CTkLabel(scroll, text="LIVE MONITORING", text_color=COLORS["text_dim"], font=font(10, "bold")
                     ).grid(row=3, column=0, sticky="w", pady=(18, 6))
        grid = ctk.CTkFrame(scroll, fg_color="transparent")
        grid.grid(row=4, column=0, sticky="ew")
        grid.grid_columnconfigure((0, 1), weight=1, uniform="ch")
        series = [(a["id"], a["name"].split()[-1], self.colors[a["id"]]) for a in self.astronauts]
        self.charts = {}
        defs = [("heart_rate", "Live Health Monitor: Heart Rate (BPM)", "BPM", (40, 140), (55, 100)),
                ("spo2", "Oxygen Saturation (%)", "%SpO2", (88, 101), (95, 100)),
                ("temperature", "Body Temperature (°C)", "°C", (35, 39.5), (36.1, 37.5))]
        slots = {"heart_rate": (0, 0), "spo2": (0, 1), "temperature": (1, 1)}
        for param, title, yl, ylim, band in defs:
            holder = Card(grid)
            r, c = slots[param]
            holder.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            ch = LiveChart(holder, title, yl, series, ylim=ylim, ref_band=band)
            ch.widget.pack(fill="both", expand=True, padx=6, pady=6)
            self.charts[param] = ch
        holder = Card(grid)
        holder.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.bar = LiveBarChart(holder, "Heart Rate Comparison (current BPM)",
                                [a["name"].split()[-1] for a in self.astronauts], (40, 140), (55, 100))
        self.bar.widget.pack(fill="both", expand=True, padx=6, pady=6)

        lower = ctk.CTkFrame(scroll, fg_color="transparent")
        lower.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        lower.grid_columnconfigure((0, 1), weight=1, uniform="l")
        self.alert_box = self._list_card(lower, "RECENT MEDICAL ALERTS", 0)
        self.timeline_box = self._list_card(lower, "MISSION ACTIVITY TIMELINE", 1)
        self._build_nasa_card(scroll)
        self._load_recent()
        self._refresh()

    # ---- cards ---------------------------------------------------------------
    def _build_nasa_card(self, scroll):
        card = Card(scroll)
        card.grid(row=6, column=0, sticky="ew", padx=4, pady=(10, 4))
        ctk.CTkLabel(card, text="NASA REFERENCE DATA BASIS", text_color=COLORS["text_dim"],
                     font=font(10, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        lines = ["Simulator behavior follows documented NASA findings:"] + [f"  • {f}" for f in NASA_FINDINGS[:3]]
        lines += ["", "Mercury flights, pre → post HR (bpm) / temp (°C):"]
        lines += [f'  {m["flight"]}: HR {m["hr_pre"]} → {m["hr_post"]}   T {m["temp_pre_c"]} → {m["temp_post_c"]}'
                  for m in MERCURY_DATA]
        lines += ["", "Sources: " + "; ".join(s["publisher"] for s in SOURCES[:4]),
                  "Variability/diurnal scaling factors are engineering assumptions, not NASA values."]
        ctk.CTkLabel(card, text="\n".join(lines), justify="left", anchor="w", text_color=COLORS["text"],
                     font=font(11), wraplength=1000).pack(anchor="w", padx=16, pady=(0, 12))

    def _list_card(self, parent, title, col):
        card = Card(parent)
        card.grid(row=0, column=col, sticky="nsew", padx=4, pady=4)
        ctk.CTkLabel(card, text=title, text_color=COLORS["text_dim"], font=font(10, "bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))
        box = ctk.CTkTextbox(card, height=170, fg_color=COLORS["card"], text_color=COLORS["text"],
                             font=font(11), wrap="word", border_width=0)
        box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for sev, c in STATUS_COLORS.items():
            box.tag_config(sev, foreground=c)
        box.configure(state="disabled")
        return box

    def _append(self, box, text, sev):
        box.configure(state="normal")
        box.insert("1.0", text + "\n", sev)
        box.configure(state="disabled")

    def _load_recent(self):
        for al in reversed(self.app.db.list_alerts(limit=8)):
            self._append(self.alert_box, f'{al["timestamp"][11:19]}  [{al["severity"].upper()}] {al["full_name"]}: {al["message"]}', al["severity"])
            self._append(self.timeline_box, f'{al["timestamp"][5:16]}  {al["code"]} {al["parameter"]} {al["severity"]}', al["severity"])
        self._append(self.timeline_box, f"{datetime.now():%m-%d %H:%M}  Monitoring session started", "info")

    # ---- live updates -------------------------------------------------------
    def on_alerts(self, alerts):
        for a in alerts:
            self._append(self.alert_box, f'{a["timestamp"]:%H:%M:%S}  [{a["severity"].upper()}] {a["name"]}: {a["message"]}', a["severity"])
            self._append(self.timeline_box, f'{a["timestamp"]:%m-%d %H:%M}  {a["code"]} {a["parameter"]} {a["severity"]}', a["severity"])

    def on_telemetry(self, batch):
        for a in self.astronauts:
            r = batch.get(a["id"])
            if not r:
                continue
            self.latest[a["id"]] = r
            st = overall_status(r)
            self.status[a["id"]] = st
            self.cards[a["id"]].update_reading(r, st)
            for param, ch in self.charts.items():
                ch.push({a["id"]: r[param]})
        self._refresh()

    def _refresh(self):
        st = list(self.status.values())
        crit, warn = st.count("critical"), st.count("warning")
        self.kpis["total"].set(len(st))
        self.kpis["healthy"].set(st.count("normal"), COLORS["normal"])
        self.kpis["attention"].set(warn, COLORS["warning"] if warn else COLORS["text"])
        self.kpis["critical"].set(crit, COLORS["critical"] if crit else COLORS["text"])
        m = self.app.active_mission()
        if m:
            start = datetime.strptime(m["launch_date"], "%Y-%m-%d")
            self.kpis["duration"].set(format_duration(datetime.now() - start))
        else:
            self.kpis["duration"].set("No active mission")
        eng = self.app.engine
        state = "PAUSED" if eng.paused else ("ONLINE" if eng.running else "OFFLINE")
        self.kpis["system"].set(state, COLORS["normal"] if state == "ONLINE" else COLORS["warning"])
        vals, cols = [], []
        for a in self.astronauts:
            r = self.latest.get(a["id"])
            vals.append(r["heart_rate"] if r else 0)
            cols.append(STATUS_COLORS[self.status[a["id"]]])
        self.bar.update(vals, cols)
        if self.app.current == "dashboard":
            for ch in self.charts.values():
                ch.redraw()
            self.bar.redraw()

    def on_show(self):
        self._refresh()
