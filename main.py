import time
import traceback
import customtkinter as ctk
from config import ACCENT_PRESETS, APP_FULL_NAME, COLORS, NAV_ITEMS
from components.dialogs import error, info
from components.login import LoginWindow
from components.sidebar import Sidebar
from components.topbar import Topbar
from core.alert_engine import AlertEngine
from core.anomaly_detector import MODEL_PATH, AnomalyDetector
from core.authentication import AuthService, can
from core.monitoring_engine import MonitoringEngine
from database.database import Database
from database.seed import seed_if_empty
from modules.ai_analysis import AIAnalysisPage
from modules.alerts import AlertsPage
from modules.analytics import AnalyticsPage
from modules.astronaut_monitoring import AstronautMonitoringPage
from modules.astronaut_profiles import AstronautProfilesPage
from modules.dashboard import DashboardPage
from modules.health_history import HealthHistoryPage
from modules.mission_management import MissionManagementPage
from modules.reports import ReportsPage
from modules.settings import SettingsPage, apply_saved_ranges
from utils.helpers import ensure_logo, overall_status
from utils.logger import get_logger

log = get_logger("app")

PAGE_CLASSES = {"dashboard": DashboardPage, "monitoring": AstronautMonitoringPage, "analytics": AnalyticsPage,
                "history": HealthHistoryPage, "ai": AIAnalysisPage, "alerts": AlertsPage,
                "profiles": AstronautProfilesPage, "missions": MissionManagementPage,
                "reports": ReportsPage, "settings": SettingsPage}
# pages that embed the astronaut list and must be rebuilt when the roster changes
ROSTER_PAGES = ("dashboard", "monitoring", "analytics", "history", "ai", "alerts", "reports")


class App(ctk.CTk):
    def __init__(self, db, user):
        super().__init__()
        self.db, self.user = db, user
        self.auth = AuthService(db)
        self.logout_requested = self.restored = False
        self.current = None
        self._mission_cache = (0.0, None)
        self._tick = 0
        self._status = {}
        self.title(APP_FULL_NAME)
        self.geometry("1440x860")
        self.minsize(1180, 720)
        self.configure(fg_color=COLORS["bg"])

        self.detector = AnomalyDetector()
        if not self.detector.load(MODEL_PATH):
            try:
                self.detector.fit(db.readings_df())
                self.detector.save(MODEL_PATH)
            except Exception:
                log.warning("Initial anomaly model training skipped: %s", traceback.format_exc(limit=1))
        self.astronauts = self._load_roster()
        self.engine = MonitoringEngine(self.astronauts, float(self.setting("monitor_interval", "1.0")),
                                       db.path, int(self.setting("persist_every", "10")))
        self.alert_engine = AlertEngine(db, self.astronauts, float(self.setting("alert_cooldown", "120")))
        self._status = {a["id"]: a["health_status"] for a in self.astronauts}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.sidebar = Sidebar(self, self.show_page)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.topbar = Topbar(self, self)
        self.topbar.grid(row=0, column=1, sticky="ew")
        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages = {}
        for key, _, _ in NAV_ITEMS:
            self._build_page(key)
        self.refresh_topbar()
        self.update_notifications()
        self.show_page("dashboard")
        self.engine.start()
        self.after(250, self._poll)
        self.protocol("WM_DELETE_WINDOW", self.close)
        if self.auth.uses_default_password(user):
            self.after(800, lambda: info(self, "Security notice", "You are using a default demo password.\nPlease change it in Settings → Account."))

    # helpers 
    def setting(self, key, default=None):
        return self.db.get_setting(key, default)

    def can(self, perm):
        return can(self.user, perm)

    def _load_roster(self):
        return [{"id": r["code"], "db_id": r["id"], "name": r["full_name"], "role": r["role"],
                 "health_status": r["health_status"]} for r in self.db.list_astronauts(active_only=True)]

    def active_mission(self):
        t, m = self._mission_cache
        if time.time() - t > 10:
            m = self.db.active_mission()
            self._mission_cache = (time.time(), m)
        return m

    def refresh_topbar(self):
        self._mission_cache = (0.0, None)
        self.topbar.set_mission(self.active_mission())

    def update_notifications(self):
        c = self.db.unack_counts()
        self.topbar.set_notifications(c["critical"] + c["warning"])

    def apply_runtime_settings(self):
        self.engine.set_interval(float(self.setting("monitor_interval", "1.0")))
        self.engine.set_persist_every(int(self.setting("persist_every", "10")))
        self.alert_engine.cooldown = float(self.setting("alert_cooldown", "120"))
        if "ai" in self.pages:
            self.pages["ai"].update_status()

    # pages
    def _build_page(self, key):
        if key in self.pages:
            self.pages[key].destroy()
        page = PAGE_CLASSES[key](self.content, self)
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = page

    def show_page(self, key, **kwargs):
        self.pages[key].tkraise()
        self.current = key
        self.sidebar.set_active(key)
        if kwargs and hasattr(self.pages[key], "preselect"):
            self.pages[key].preselect(**kwargs)
        self.pages[key].on_show()

    def refresh_astronauts(self):
        self.astronauts = self._load_roster()
        self.engine.sync_astronauts(self.astronauts)
        self.alert_engine.set_roster(self.astronauts)
        self._status = {a["id"]: a["health_status"] for a in self.astronauts}
        cur = self.current
        for key in ROSTER_PAGES:
            self._build_page(key)
        self.show_page(cur or "dashboard")

    # telemetry loop 
    def _poll(self):
        try:
            batches = self.engine.drain()
            changed = False
            for batch in batches:
                self._tick += 1
                new_alerts = self.alert_engine.process(batch)
                if self.setting("ai_live", "1") == "1" and self.detector.ready and self._tick % 5 == 0:
                    for code, (score, flag, reasons) in self.detector.score_batch(batch).items():
                        if flag:
                            a = self.alert_engine.emit_ai(code, score, reasons)
                            if a:
                                new_alerts.append(a)
                for a in self.astronauts:
                    r = batch.get(a["id"])
                    if r:
                        st = overall_status(r)
                        if st != self._status.get(a["id"]):
                            self._status[a["id"]] = st
                            self.db.set_health_status(a["db_id"], st)
                for key in ROSTER_PAGES:
                    self.pages[key].on_telemetry(batch)
                if new_alerts:
                    changed = True
                    for key in ROSTER_PAGES:
                        self.pages[key].on_alerts(new_alerts)
            if changed:
                self.update_notifications()
        except Exception:
            log.exception("Polling error")
        self.after(250, self._poll)

    # lifecycle
    def logout(self):
        self.logout_requested = True
        self.db.log("INFO", "auth", f'User {self.user["username"]} logged out', self.user["id"])
        self.close()

    def close(self):
        self.engine.stop()
        self.destroy()


def load_startup_settings(db):
    apply_saved_ranges(db)
    accent = db.get_setting("accent")
    if accent in ACCENT_PRESETS.values():
        COLORS["primary"] = accent
    try:
        scale = float(db.get_setting("ui_scale", "1.0"))
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
    except ValueError:
        pass


def main():
    ctk.set_appearance_mode("dark")
    ensure_logo()
    db = Database()
    try:
        seed_if_empty(db)
        load_startup_settings(db)
        while True:
            user = LoginWindow(db).run()
            if not user:
                break
            app = App(db, user)
            app.mainloop()
            if app.restored or not app.logout_requested:
                break
    finally:
        db.close()
print("FOR ADMIN INTERFACE")
print("username = admin")
print("Password = admin123")

print("FOR MEDICAL OFFICER INTERFACE")
print("username = medic")
print("Password = medic123")

if __name__ == "__main__":
    main()
