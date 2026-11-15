import customtkinter as ctk
from config import COLORS, STATUS_COLORS
from components.cards import StatCard, font, ghost_button, labeled_combo, primary_button
from components.dialogs import confirm, info
from components.table import DataTable
from modules.base_page import BasePage

PAGE = 200


class AlertsPage(BasePage):
    title = "Alerts & Notifications"
    subtitle = "Threshold and AI alerts. Acknowledge to clear the notification counter."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.offset = 0
        kp = ctk.CTkFrame(self.body, fg_color="transparent")
        kp.pack(fill="x")
        self.kpis = {}
        for i, (k, t, c) in enumerate((("critical", "Critical (unack.)", COLORS["critical"]), ("warning", "Warning (unack.)", COLORS["warning"]),
                                       ("info", "Info (unack.)", COLORS["primary"]), ("total", "Total alerts", COLORS["secondary"]))):
            kp.grid_columnconfigure(i, weight=1, uniform="a")
            c_ = StatCard(kp, t, "0", c, "▲")
            c_.grid(row=0, column=i, sticky="ew", padx=4)
            self.kpis[k] = c_
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x", pady=8)
        f, self.sev_cb = labeled_combo(bar, "Severity", ["All", "critical", "warning", "info", "normal"], 120); f.pack(side="left", padx=4)
        f, self.astro_cb = labeled_combo(bar, "Astronaut", ["All"] + [a["id"] for a in app.astronauts], 120); f.pack(side="left", padx=4)
        f, self.ack_cb = labeled_combo(bar, "Status", ["All", "Unacknowledged", "Acknowledged"], 150); f.pack(side="left", padx=4)
        primary_button(bar, "Apply", self.apply, 80).pack(side="left", padx=6, pady=(16, 0))
        ghost_button(bar, "Acknowledge all", self.ack_all, 130).pack(side="right", padx=3, pady=(16, 0))
        ghost_button(bar, "Acknowledge selected", self.ack_selected, 160).pack(side="right", padx=3, pady=(16, 0))
        self.table = DataTable(self.body, [("timestamp", "Time", 130), ("severity", "Severity", 75), ("code", "Astronaut", 70),
                                           ("full_name", "Name", 140), ("message", "Description", 470),
                                           ("source", "Source", 70), ("ack", "Ack", 45)], height=16)
        self.table.pack(fill="both", expand=True)
        nav = ctk.CTkFrame(self.body, fg_color="transparent")
        nav.pack(fill="x", pady=(6, 0))
        ghost_button(nav, "◀ Newer", lambda: self.page(-1), 90).pack(side="left")
        self.page_lbl = ctk.CTkLabel(nav, text="", text_color=COLORS["text_dim"], font=font(11))
        self.page_lbl.pack(side="left", padx=10)
        ghost_button(nav, "Older ▶", lambda: self.page(1), 90).pack(side="left")
        self.refresh()

    def _filters(self):
        sev = None if self.sev_cb.get() == "All" else self.sev_cb.get()
        code = self.astro_cb.get()
        aid = next((a["db_id"] for a in self.app.astronauts if a["id"] == code), None) if code != "All" else None
        ack = {"All": None, "Unacknowledged": False, "Acknowledged": True}[self.ack_cb.get()]
        return sev, aid, ack

    def apply(self):
        self.offset = 0
        self.refresh()

    def page(self, d):
        n = self.offset + d * PAGE
        if n >= 0 and (d < 0 or n < self.total):
            self.offset = n
            self.refresh()

    def refresh(self):
        db = self.app.db
        sev, aid, ack = self._filters()
        rows = db.list_alerts(sev, aid, ack, PAGE, self.offset)
        self.total = db.count_alerts(sev, aid, ack)
        for r in rows:
            r["ack"] = "✔" if r["acknowledged"] else "•"
        self.table.set_rows(rows, tag_key="severity")
        un = db.unack_counts()
        for k in ("critical", "warning", "info"):
            self.kpis[k].set(un[k], STATUS_COLORS[k] if un[k] else COLORS["text"])
        self.kpis["total"].set(db.count_alerts())
        self.page_lbl.configure(text=f"{self.offset + 1 if self.total else 0}-{min(self.offset + PAGE, self.total)} of {self.total}")
        self.app.update_notifications()

    def ack_selected(self):
        rows = self.table.selected_rows()
        if not rows:
            return info(self, "Acknowledge", "Select one or more alerts first.")
        for r in rows:
            self.app.db.ack_alert(r["id"], self.app.user["id"])
        self.app.db.log("INFO", "alerts", f"Acknowledged {len(rows)} alert(s)", self.app.user["id"])
        self.refresh()

    def ack_all(self):
        if confirm(self, "Acknowledge all", "Acknowledge ALL outstanding alerts?"):
            self.app.db.ack_all(self.app.user["id"])
            self.refresh()

    def on_alerts(self, alerts):
        if self.app.current == "alerts":
            self.refresh()

    def on_show(self):
        self.refresh()
