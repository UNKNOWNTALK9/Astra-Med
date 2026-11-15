import time
from collections import deque
import customtkinter as ctk
from config import ASTRONAUT_COLORS, COLORS, PARAM_KEYS, REFERENCE_RANGES, SIMULATION_NOTICE, STATUS_COLORS
from components.cards import Card, font, ghost_button, primary_button, tip
from components.charts import LiveChart
from core.telemetry_simulator import EcgGenerator
from modules.base_page import BasePage
from utils.helpers import overall_status, param_status


class ParamTile(Card):
    def __init__(self, parent, param):
        super().__init__(parent, corner_radius=12)
        meta = REFERENCE_RANGES[param]
        self.param = param
        ctk.CTkLabel(self, text=meta["label"].upper(), text_color=COLORS["text_dim"], font=font(9, "bold")
                     ).pack(anchor="w", padx=12, pady=(8, 0))
        self.value = ctk.CTkLabel(self, text="--", text_color=COLORS["text"], font=font(22, "bold"))
        self.value.pack(anchor="w", padx=12)
        self.range_lbl = ctk.CTkLabel(self, text="", text_color=COLORS["text_dim"], font=font(9))
        self.range_lbl.pack(anchor="w", padx=12, pady=(0, 8))
        self.refresh_range()

    def refresh_range(self):
        m = REFERENCE_RANGES[self.param]
        self.range_lbl.configure(text=f'{m["unit"]}   normal {m["range"][1]}–{m["range"][2]}')

    def set(self, value):
        st = param_status(self.param, value)
        dec = 0 if self.param in ("heart_rate", "systolic", "diastolic") else 1
        self.value.configure(text=f"{value:.{dec}f}", text_color=STATUS_COLORS[st] if st != "normal" else COLORS["text"])
        self.configure(border_color=STATUS_COLORS[st] if st != "normal" else COLORS["border"])


class AstronautMonitoringPage(BasePage):
    title = "Astronaut Monitoring"
    subtitle = SIMULATION_NOTICE

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.astronauts = app.astronauts
        self.hist = {a["id"]: {k: deque(maxlen=60) for k in ("heart_rate", "spo2", "systolic", "diastolic")}
                     for a in self.astronauts}
        self.latest, self.status = {}, {}
        self.selected = self.astronauts[0]["id"] if self.astronauts else None
        self.ecg_gen, self.last_tick = EcgGenerator(), time.monotonic()

        self.body.grid_columnconfigure(1, weight=1)
        self.body.grid_rowconfigure(0, weight=1)
        left = Card(self.body, width=230)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        left.grid_propagate(False)
        ctk.CTkLabel(left, text="CREW", text_color=COLORS["text_dim"], font=font(10, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.buttons = {}
        for i, a in enumerate(self.astronauts):
            b = ctk.CTkButton(left, text=f'● {a["name"]}', anchor="w", height=36, corner_radius=8, fg_color="transparent",
                              hover_color=COLORS["card_hover"], text_color=COLORS["text"], font=font(12),
                              command=lambda c=a["id"]: self.select(c))
            b.pack(fill="x", padx=8, pady=2)
            self.buttons[a["id"]] = b
        self.pause_btn = ghost_button(left, "⏸ Pause monitoring", self._toggle_pause, 190)
        self.pause_btn.pack(side="bottom", pady=12)
        tip(self.pause_btn, "Pause or resume the background telemetry thread")

        right = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        self.name_lbl = ctk.CTkLabel(head, text="", text_color=COLORS["text"], font=font(18, "bold"))
        self.name_lbl.pack(side="left")
        self.badge = ctk.CTkLabel(head, text="", font=font(11, "bold"))
        self.badge.pack(side="left", padx=12)
        ghost_button(head, "Reference ranges", lambda: app.show_page("settings", tab="Alert Thresholds"), 130).pack(side="right", padx=4)
        ghost_button(head, "Health history", self._open_history, 120).pack(side="right", padx=4)

        tiles = ctk.CTkFrame(right, fg_color="transparent")
        tiles.grid(row=1, column=0, sticky="ew", pady=10)
        self.tiles = {}
        for i, p in enumerate(PARAM_KEYS):
            tiles.grid_columnconfigure(i % 5, weight=1, uniform="t")
            t = ParamTile(tiles, p)
            t.grid(row=i // 5, column=i % 5, sticky="ew", padx=4, pady=4)
            self.tiles[p] = t
        self.bp_text = ctk.CTkLabel(right, text="", text_color=COLORS["text_dim"], font=font(11))
        self.bp_text.grid(row=2, column=0, sticky="w")

        charts = ctk.CTkFrame(right, fg_color="transparent")
        charts.grid(row=3, column=0, sticky="ew")
        charts.grid_columnconfigure((0, 1), weight=1, uniform="c")
        hol = Card(charts)
        hol.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        self.ecg = LiveChart(hol, "ECG (synthetic single-lead waveform, illustrative)", "mV", [("ecg", "ECG", COLORS["normal"])],
                             ylim=(-0.5, 1.3), max_points=500)
        self.ecg.widget.pack(fill="both", expand=True, padx=6, pady=6)
        self.mini = {}
        for col, (key, title, series, ylim) in enumerate([
                ("hr", "Heart Rate / SpO2 (last 60 samples)", [("heart_rate", "HR", COLORS["primary"])], (40, 140)),
                ("bp", "Blood Pressure (mmHg)", [("systolic", "Systolic", COLORS["critical"]), ("diastolic", "Diastolic", COLORS["secondary"])], (50, 160))]):
            h = Card(charts)
            h.grid(row=1, column=col, sticky="nsew", padx=4, pady=4)
            ch = LiveChart(h, title, "", series, ylim=ylim)
            ch.widget.pack(fill="both", expand=True, padx=6, pady=6)
            self.mini[key] = ch
        self.select(self.selected)

    def select(self, code):
        if not code:
            return
        self.selected = code
        a = next(x for x in self.astronauts if x["id"] == code)
        self.name_lbl.configure(text=f'{a["name"]}  ·  {a["role"]}')
        for c, b in self.buttons.items():
            b.configure(fg_color=COLORS["card_hover"] if c == code else "transparent")
        self.ecg.load("ecg", [])
        self.ecg_gen = EcgGenerator()
        for k, ch in self.mini.items():
            for s in ch.keys:
                ch.load(s, self.hist[code][s])
        if code in self.latest:
            self._show(self.latest[code])

    def _open_history(self):
        a = next((x for x in self.astronauts if x["id"] == self.selected), None)
        if a:
            self.app.show_page("history", astronaut_code=a["id"])

    def _toggle_pause(self):
        eng = self.app.engine
        if eng.paused:
            eng.resume(); self.pause_btn.configure(text="⏸ Pause monitoring")
        else:
            eng.pause(); self.pause_btn.configure(text="▶ Resume monitoring")

    def _show(self, r):
        for p, t in self.tiles.items():
            t.set(r[p])
        st = overall_status(r)
        self.badge.configure(text=f"● {st.upper()}", text_color=STATUS_COLORS[st])
        self.bp_text.configure(text=f'Blood pressure {r["systolic"]:.0f}/{r["diastolic"]:.0f} mmHg   ·   '
                                    f'Pulse pressure {r["systolic"] - r["diastolic"]:.0f}   ·   {SIMULATION_NOTICE}')

    def on_telemetry(self, batch):
        now = time.monotonic()
        dt = min(max(now - self.last_tick, 0.2), 3.0)
        self.last_tick = now
        for a in self.astronauts:
            r = batch.get(a["id"])
            if not r:
                continue
            self.latest[a["id"]] = r
            st = overall_status(r)
            self.status[a["id"]] = st
            self.buttons[a["id"]].configure(text=f'● {a["name"]}', text_color=STATUS_COLORS[st] if st != "normal" else COLORS["text"])
            for k in self.hist[a["id"]]:
                self.hist[a["id"]][k].append(r[k])
        r = self.latest.get(self.selected)
        if not r:
            return
        for ch in self.mini.values():
            for s in ch.keys:
                ch.load(s, self.hist[self.selected][s])
        self.ecg.push_many("ecg", self.ecg_gen.chunk(r["heart_rate"], dt))
        self._show(r)
        if self.app.current == "monitoring":
            self.ecg.redraw()
            for ch in self.mini.values():
                ch.redraw()

    def on_show(self):
        for t in self.tiles.values():
            t.refresh_range()
