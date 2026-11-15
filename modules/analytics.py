from datetime import datetime, timedelta
import customtkinter as ctk
import numpy as np
import seaborn as sns
from config import ASTRONAUT_COLORS, COLORS, PARAM_KEYS, REFERENCE_RANGES
from components.cards import font, labeled_combo, labeled_entry, primary_button
from components.charts import ChartPanel
from components.table import DataTable
from core import analytics_engine as ae
from modules.base_page import BasePage
from utils.validators import ValidationError, validate_date
from components.dialogs import error

RANGES = {"Last 24 hours": 1, "Last 7 days": 7, "Last 30 days": 30, "All data": None, "Custom": -1}
TABS = ["Trends", "Vital Overview", "Blood Pressure", "Sleep", "Correlation", "Comparison", "Statistics"]


class AnalyticsPage(BasePage):
    title = "Vital Signs Analytics"
    subtitle = "Trends, comparisons and correlations (simulated data). Use the toolbar to zoom and pan."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.df = None
        self.color_of = {}
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        names = ["All astronauts"] + [f'{a["id"]} {a["name"]}' for a in app.astronauts]
        self._names = names
        f, self.astro_cb = labeled_combo(bar, "Astronaut", names, 220); f.pack(side="left", padx=4)
        f, self.range_cb = labeled_combo(bar, "Date range", list(RANGES), 130, lambda v: None); f.pack(side="left", padx=4)
        self.range_cb.set("Last 7 days")
        f, self.from_e = labeled_entry(bar, "From (custom)", 95); f.pack(side="left", padx=4)
        f, self.to_e = labeled_entry(bar, "To (custom)", 95); f.pack(side="left", padx=4)
        f, self.gran_cb = labeled_combo(bar, "Granularity", list(ae.GRANULARITY), 100); f.pack(side="left", padx=4)
        self.gran_cb.set("Hourly")
        f, self.param_cb = labeled_combo(bar, "Parameter", [REFERENCE_RANGES[p]["label"] for p in PARAM_KEYS], 130); f.pack(side="left", padx=4)
        ctk.CTkLabel(bar, text="").pack(side="left", expand=True)
        primary_button(bar, "Apply", self.apply, 90).pack(side="right", padx=4, pady=(16, 0))
        self.tabs = ctk.CTkTabview(self.body, fg_color=COLORS["card"], command=self._on_tab)
        self.tabs.pack(fill="both", expand=True)
        self.panels = {}
        for t in TABS:
            tab = self.tabs.add(t)
            if t == "Statistics":
                self.stats_table = DataTable(tab, [("label", "Parameter", 140), ("unit", "Unit", 70), ("min", "Min", 80),
                                                   ("mean", "Mean", 80), ("max", "Max", 80), ("std", "Std", 80),
                                                   ("out_pct", "% out of range", 110), ("range", "Normal range", 110)], height=12)
                self.stats_table.pack(fill="both", expand=True, padx=8, pady=8)
            else:
                p = ChartPanel(tab)
                p.pack(fill="both", expand=True, padx=4, pady=4)
                self.panels[t] = p
        self.drawn = set()
        self.apply()

    # data
    def _param(self):
        label = self.param_cb.get()
        return next(p for p in PARAM_KEYS if REFERENCE_RANGES[p]["label"] == label)

    def apply(self):
        try:
            r = RANGES[self.range_cb.get()]
            end = datetime.now()
            start = None
            if r == -1:
                start = datetime.strptime(validate_date(self.from_e.get(), "From"), "%Y-%m-%d")
                end = datetime.strptime(validate_date(self.to_e.get(), "To"), "%Y-%m-%d") + timedelta(days=1)
            elif r:
                start = end - timedelta(days=r)
        except ValidationError as e:
            return error(self, "Date range", str(e))
        sel = self.astro_cb.get()
        ids = None
        if sel != "All astronauts":
            code = sel.split()[0]
            ids = [a["db_id"] for a in self.app.astronauts if a["id"] == code]
        self.df = self.app.db.readings_df(ids, start, end)
        codes = sorted(self.df["code"].unique()) if not self.df.empty else []
        self.color_of = {c: ASTRONAUT_COLORS[i % len(ASTRONAUT_COLORS)] for i, c in enumerate(sorted({a["id"] for a in self.app.astronauts}))}
        self.drawn.clear()
        self.stats_table.set_rows(ae.summary_stats(self.df).to_dict("records") if not self.df.empty else [],
                                  fmt=lambda k, r: (f"{r[k]:.2f}" if isinstance(r[k], float) else r[k]))
        self._on_tab()

    def _on_tab(self):
        t = self.tabs.get()
        if t in self.drawn or t == "Statistics":
            return
        self.drawn.add(t)
        if self.df is None or self.df.empty:
            if t in self.panels:
                self.panels[t].message("No data in the selected range")
            return
        getattr(self, "_draw_" + t.lower().replace(" ", "_"))(self.panels[t])

    # chart builders 
    def _lines(self, ax, param, freq):
        wide = ae.resample_param(self.df, param, freq)
        for code in wide.columns:
            ax.plot(wide.index, wide[code], lw=1.3, color=self.color_of.get(code), label=code)
        lo, hi = REFERENCE_RANGES[param]["range"][1:3]
        ax.axhspan(lo, hi, color=COLORS["normal"], alpha=0.07, lw=0)
        ax.legend(fontsize=7, frameon=False, ncol=5, loc="upper left")

    def _draw_trends(self, panel):
        p, freq = self._param(), ae.GRANULARITY[self.gran_cb.get()]
        meta = REFERENCE_RANGES[p]

        def f(fig):
            ax = fig.add_subplot(111)
            self._lines(ax, p, freq)
            ax.set_title(f'{meta["label"]} trend ({self.gran_cb.get()})', loc="left", fontsize=10, fontweight="bold")
            ax.set_ylabel(meta["unit"])
            fig.autofmt_xdate()
        panel.draw(f)

    def _draw_vital_overview(self, panel):
        freq = ae.GRANULARITY[self.gran_cb.get()]

        def f(fig):
            for i, p in enumerate(("heart_rate", "spo2", "temperature", "resp_rate")):
                ax = fig.add_subplot(2, 2, i + 1)
                self._lines(ax, p, freq)
                ax.set_title(REFERENCE_RANGES[p]["label"], loc="left", fontsize=9, fontweight="bold")
                if i > 0:
                    ax.get_legend().remove()
            fig.autofmt_xdate()
            fig.tight_layout()
        panel.draw(f)

    def _draw_blood_pressure(self, panel):
        freq = ae.GRANULARITY[self.gran_cb.get()]
        d = self.df.set_index("timestamp")[["systolic", "diastolic"]]
        d = d.resample(freq).mean() if freq else d
        d["map"] = (d["systolic"] + 2 * d["diastolic"]) / 3

        def f(fig):
            ax = fig.add_subplot(111)
            ax.plot(d.index, d["systolic"], color=COLORS["critical"], lw=1.2, label="Systolic")
            ax.plot(d.index, d["diastolic"], color=COLORS["secondary"], lw=1.2, label="Diastolic")
            ax.plot(d.index, d["map"], color=COLORS["primary"], lw=1.0, ls="--", label="Mean arterial")
            ax.axhspan(*REFERENCE_RANGES["systolic"]["range"][1:3], color=COLORS["critical"], alpha=0.05, lw=0)
            ax.axhspan(*REFERENCE_RANGES["diastolic"]["range"][1:3], color=COLORS["secondary"], alpha=0.06, lw=0)
            ax.set_title("Blood pressure (pooled over selected astronauts)", loc="left", fontsize=10, fontweight="bold")
            ax.set_ylabel("mmHg")
            ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
            fig.autofmt_xdate()
        panel.draw(f)

    def _draw_sleep(self, panel):
        wide = ae.daily_sleep(self.df)

        def f(fig):
            ax = fig.add_subplot(111)
            n = max(len(wide.columns), 1)
            w = 0.8 / n
            x = np.arange(len(wide.index))
            for i, c in enumerate(wide.columns):
                ax.bar(x + i * w, wide[c], width=w, color=self.color_of.get(c), label=c)
            ax.axhline(REFERENCE_RANGES["sleep"]["range"][1], color=COLORS["warning"], ls="--", lw=1)
            step = max(1, len(x) // 10)
            ax.set_xticks(x[::step] + 0.4)
            ax.set_xticklabels([d.strftime("%m-%d") for d in wide.index[::step]], fontsize=7)
            ax.set_title("Nightly sleep duration (h); dashed = lower normal limit", loc="left", fontsize=10, fontweight="bold")
            ax.legend(fontsize=7, frameon=False, ncol=5)
        panel.draw(f)

    def _draw_correlation(self, panel):
        corr = ae.correlation(self.df)

        def f(fig):
            ax = fig.add_subplot(111)
            sns.heatmap(corr, ax=ax, cmap="coolwarm", center=0, annot=True, fmt=".2f", annot_kws={"size": 7},
                        cbar_kws={"shrink": 0.8}, linewidths=0.4, linecolor=COLORS["card"])
            ax.set_title("Parameter correlation (Pearson)", loc="left", fontsize=10, fontweight="bold")
            ax.tick_params(labelsize=7)
            for cb in fig.axes[1:]:
                cb.tick_params(colors=COLORS["text_dim"], labelsize=7)
        panel.draw(f)

    def _draw_comparison(self, panel):
        p = self._param()
        freq = ae.GRANULARITY[self.gran_cb.get()] or "D"
        per = ae.period_comparison(self.df, p, freq, 14)
        avg = ae.astronaut_comparison(self.df, [p])[p]
        meta = REFERENCE_RANGES[p]

        def f(fig):
            ax1, ax2 = fig.add_subplot(121), fig.add_subplot(122)
            x = np.arange(len(per.index))
            n = max(len(per.columns), 1)
            w = 0.8 / n
            for i, c in enumerate(per.columns):
                ax1.bar(x + i * w, per[c], width=w, color=self.color_of.get(c), label=c)
            step = max(1, len(x) // 7)
            ax1.set_xticks(x[::step] + 0.4)
            ax1.set_xticklabels([d.strftime("%m-%d") for d in per.index[::step]], fontsize=7)
            ax1.set_ylim(per.min().min() * 0.97, per.max().max() * 1.03)
            ax1.set_title(f'{meta["label"]}: last {len(per)} periods', loc="left", fontsize=9, fontweight="bold")
            ax1.legend(fontsize=6, frameon=False, ncol=3)
            ax2.bar(avg.index, avg.values, color=[self.color_of.get(c) for c in avg.index])
            ax2.axhspan(*meta["range"][1:3], color=COLORS["normal"], alpha=0.08, lw=0)
            ax2.set_ylim(avg.min() * 0.95, avg.max() * 1.05)
            ax2.set_title("Astronaut-to-astronaut (mean)", loc="left", fontsize=9, fontweight="bold")
            ax2.tick_params(axis="x", labelsize=7)
            fig.tight_layout()
        panel.draw(f)

    def on_show(self):
        pass
