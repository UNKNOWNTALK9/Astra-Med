"""Matplotlib charts embedded in Tk. Lines are updated in place (set_data) rather
than rebuilt, and redraws are skipped while the chart is hidden."""
from collections import deque

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

from config import COLORS


class LiveChart:
    def __init__(self, parent, title, ylabel, series, ylim=None,
                 ref_band=None, max_points=60):
        """series: list of (key, label, color). ref_band: (low, high) shaded normal range."""
        self.max_points = max_points
        self.keys = [s[0] for s in series]
        self.data = {k: deque(maxlen=max_points) for k in self.keys}
        self.fig = Figure(figsize=(4, 2.4), dpi=100, facecolor=COLORS["card"])
        self.ax = self.fig.add_subplot(111)
        ax = self.ax
        ax.set_facecolor(COLORS["card"])
        ax.set_title(title, color=COLORS["text"], fontsize=10, loc="left", fontweight="bold", pad=8)
        ax.tick_params(colors=COLORS["text_dim"], labelsize=8, length=0)
        ax.grid(True, color=COLORS["border"], linewidth=0.6, alpha=0.7)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_ylabel(ylabel, color=COLORS["text_dim"], fontsize=8)
        ax.set_xlim(0, max_points - 1)
        ax.set_xticklabels([])
        if ylim:
            ax.set_ylim(*ylim)
        if ref_band:
            ax.axhspan(ref_band[0], ref_band[1], color=COLORS["normal"], alpha=0.07, lw=0)
        self.lines = {}
        for key, label, color in series:
            (ln,) = ax.plot([], [], color=color, linewidth=1.6, label=label)
            self.lines[key] = ln
        if len(series) > 1:
            leg = ax.legend(loc="upper left", fontsize=7, frameon=False, ncol=len(series))
            for t in leg.get_texts():
                t.set_color(COLORS["text_dim"])
        self.fig.subplots_adjust(left=0.1, right=0.98, top=0.86, bottom=0.08)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.widget = self.canvas.get_tk_widget()
        self.widget.configure(bg=COLORS["card"], highlightthickness=0)

    def push_many(self, key, values):
        self.data[key].extend(values)

    def load(self, key, values):
        self.data[key].clear()
        self.data[key].extend(values)

    def push(self, values: dict):
        for k, v in values.items():
            if k in self.data:
                self.data[k].append(v)

    def redraw(self):
        if not self.widget.winfo_ismapped():
            return
        for k, ln in self.lines.items():
            d = self.data[k]
            ln.set_data(range(len(d)), list(d))
        self.canvas.draw_idle()


def style_axes(ax):
    ax.set_facecolor(COLORS["card"])
    ax.tick_params(colors=COLORS["text_dim"], labelsize=8, length=0)
    ax.grid(True, color=COLORS["border"], linewidth=0.6, alpha=0.7)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.title.set_color(COLORS["text"])
    ax.xaxis.label.set_color(COLORS["text_dim"])
    ax.yaxis.label.set_color(COLORS["text_dim"])
    leg = ax.get_legend()
    if leg:
        leg.get_frame().set_alpha(0)
        for t in leg.get_texts():
            t.set_color(COLORS["text_dim"])


class LiveBarChart:
    """Bar chart whose bars are updated in place (e.g. current heart rate per astronaut)."""

    def __init__(self, parent, title, labels, ylim, ref_band=None):
        self.labels = labels
        self.fig = Figure(figsize=(4, 2.4), dpi=100, facecolor=COLORS["card"])
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title(title, color=COLORS["text"], fontsize=10, loc="left", fontweight="bold", pad=8)
        self.ax.set_ylim(*ylim)
        if ref_band:
            self.ax.axhspan(ref_band[0], ref_band[1], color=COLORS["normal"], alpha=0.07, lw=0)
        self.bars = self.ax.bar(range(len(labels)), [0] * len(labels), color=COLORS["primary"], width=0.55)
        self.ax.set_xticks(range(len(labels)))
        self.ax.set_xticklabels(labels, fontsize=7)
        style_axes(self.ax)
        self.ax.grid(axis="x", visible=False)
        self.fig.subplots_adjust(left=0.1, right=0.98, top=0.86, bottom=0.14)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.widget = self.canvas.get_tk_widget()
        self.widget.configure(bg=COLORS["card"], highlightthickness=0)

    def update(self, values, colors):
        for bar, v, c in zip(self.bars, values, colors):
            bar.set_height(v)
            bar.set_color(c)

    def redraw(self):
        if self.widget.winfo_ismapped():
            self.canvas.draw_idle()


class ChartPanel(ctk.CTkFrame):
    """Static matplotlib figure with zoom/pan toolbar; draw(fn) redraws on the same canvas."""

    def __init__(self, parent, figsize=(6, 3.2), toolbar=True):
        super().__init__(parent, fg_color=COLORS["card"], corner_radius=10)
        self.fig = Figure(figsize=figsize, dpi=100, facecolor=COLORS["card"])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().configure(bg=COLORS["card"], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        if toolbar:
            tb = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            try:
                tb.config(background=COLORS["card"])
                for w in tb.winfo_children():
                    try:
                        w.config(background=COLORS["card"])
                    except Exception:
                        pass
            except Exception:
                pass
            tb.pack(side="bottom", fill="x")

    def draw(self, fn):
        self.fig.clear()
        try:
            fn(self.fig)
        finally:
            for ax in self.fig.axes:
                style_axes(ax)
            self.canvas.draw_idle()

    def message(self, text):
        def _f(fig):
            ax = fig.add_subplot(111)
            ax.axis("off")
            ax.text(0.5, 0.5, text, ha="center", va="center", color=COLORS["text_dim"], fontsize=10)
        self.draw(_f)
