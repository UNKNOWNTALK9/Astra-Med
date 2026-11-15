import customtkinter as ctk
from tkinter import filedialog

from config import (ACCENT_PRESETS, BACKUP_DIR, COLORS, DEFAULT_RANGES, EXPORT_DIR, PARAM_KEYS, REFERENCE_RANGES,
                    ROLE_LABELS, ROLES, VERSION)
from components.cards import Card, danger_button, font, ghost_button, labeled_combo, primary_button
from components.dialogs import FormDialog, confirm, error, info
from components.table import DataTable
from modules.base_page import BasePage
from services import backup_service, export_service
from utils.helpers import open_path
from utils.validators import ValidationError, validate_float, validate_password

TABS = ["Appearance", "Monitoring", "Alert Thresholds", "Users", "Account", "Data & Backup", "Logs"]


def apply_saved_ranges(db):
    saved = db.get_json_setting("reference_ranges", {})
    for p, vals in saved.items():
        if p in REFERENCE_RANGES and len(vals) == 4:
            REFERENCE_RANGES[p]["range"] = tuple(vals)


class SettingsPage(BasePage):
    title = "System Settings"
    subtitle = "Administration, thresholds, security and data management"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.tabs = ctk.CTkTabview(self.body, fg_color=COLORS["card"])
        self.tabs.pack(fill="both", expand=True)
        for t in TABS:
            self.tabs.add(t)
        self._appearance(self.tabs.tab("Appearance"))
        self._monitoring(self.tabs.tab("Monitoring"))
        self._thresholds(self.tabs.tab("Alert Thresholds"))
        self._users(self.tabs.tab("Users"))
        self._account(self.tabs.tab("Account"))
        self._data(self.tabs.tab("Data & Backup"))
        self._logs(self.tabs.tab("Logs"))

    def preselect(self, tab=None, **_):
        if tab in TABS:
            self.tabs.set(tab)

    def on_show(self):
        self.load_logs()
        self.load_users()

    def _deny(self, what="administrators"):
        error(self, "Not permitted", f"Only {what} can do this.")

    # ---- appearance ---------------------------------------------------------------
    def _appearance(self, tab):
        db = self.app.db
        f, self.accent_cb = labeled_combo(tab, "Accent color (applies after restart)", list(ACCENT_PRESETS), 220)
        f.pack(anchor="w", padx=16, pady=(16, 6))
        cur = db.get_setting("accent", ACCENT_PRESETS["Sky"])
        self.accent_cb.set(next((k for k, v in ACCENT_PRESETS.items() if v == cur), "Sky"))
        f, self.scale_cb = labeled_combo(tab, "Interface scale (applies immediately)", ["80%", "90%", "100%", "110%", "120%"], 220)
        f.pack(anchor="w", padx=16, pady=6)
        self.scale_cb.set(f'{int(float(db.get_setting("ui_scale", "1.0")) * 100)}%')
        primary_button(tab, "Save appearance", self.save_appearance, 160).pack(anchor="w", padx=16, pady=12)
        ctk.CTkLabel(tab, text=f"ASTRA-MED {VERSION}  ·  Dark mission-control theme", text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w", padx=16)

    def save_appearance(self):
        db = self.app.db
        db.set_setting("accent", ACCENT_PRESETS[self.accent_cb.get()])
        scale = int(self.scale_cb.get().rstrip("%")) / 100
        db.set_setting("ui_scale", scale)
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
        info(self, "Appearance", "Saved. The accent color takes effect after restarting the application.")

    # ---- monitoring ---------------------------------------------------------------
    def _monitoring(self, tab):
        a = self.app
        ctk.CTkLabel(tab, text="Monitoring interval (seconds)", text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w", padx=16, pady=(16, 0))
        self.interval = ctk.CTkSlider(tab, from_=0.5, to=5.0, number_of_steps=9, width=300)
        self.interval.set(float(a.setting("monitor_interval", "1.0")))
        self.interval.pack(anchor="w", padx=16)
        self.int_lbl = ctk.CTkLabel(tab, text="", text_color=COLORS["text"], font=font(11))
        self.int_lbl.pack(anchor="w", padx=16)
        self.interval.configure(command=lambda v: self.int_lbl.configure(text=f"{float(v):.1f} s"))
        self.int_lbl.configure(text=f"{self.interval.get():.1f} s")
        ctk.CTkLabel(tab, text="Store one reading to the database every N ticks", text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w", padx=16, pady=(14, 0))
        self.persist = ctk.CTkSlider(tab, from_=1, to=60, number_of_steps=59, width=300)
        self.persist.set(int(a.setting("persist_every", "10")))
        self.persist.pack(anchor="w", padx=16)
        self.per_lbl = ctk.CTkLabel(tab, text="", text_color=COLORS["text"], font=font(11))
        self.per_lbl.pack(anchor="w", padx=16)
        self.persist.configure(command=lambda v: self.per_lbl.configure(text=f"every {int(v)} ticks"))
        self.per_lbl.configure(text=f"every {int(self.persist.get())} ticks")
        self.ai_sw = ctk.CTkSwitch(tab, text="Live AI anomaly scoring (creates info alerts)", font=font(12))
        if a.setting("ai_live", "1") == "1":
            self.ai_sw.select()
        self.ai_sw.pack(anchor="w", padx=16, pady=14)
        ctk.CTkLabel(tab, text="Alert cooldown (seconds) before the same alert can re-fire", text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w", padx=16)
        self.cool = ctk.CTkEntry(tab, width=100)
        self.cool.insert(0, a.setting("alert_cooldown", "120"))
        self.cool.pack(anchor="w", padx=16, pady=(0, 10))
        primary_button(tab, "Apply monitoring settings", self.save_monitoring, 200).pack(anchor="w", padx=16, pady=8)

    def save_monitoring(self):
        if not self.can("edit_thresholds"):
            return self._deny("authorised staff")
        try:
            cd = validate_float(self.cool.get(), "Cooldown", 0, 3600)
        except ValidationError as e:
            return error(self, "Settings", str(e))
        db = self.app.db
        db.set_setting("monitor_interval", round(self.interval.get(), 1))
        db.set_setting("persist_every", int(self.persist.get()))
        db.set_setting("ai_live", "1" if self.ai_sw.get() else "0")
        db.set_setting("alert_cooldown", int(cd))
        self.app.apply_runtime_settings()
        db.log("INFO", "settings", "Monitoring settings changed", self.app.user["id"])
        info(self, "Settings", "Monitoring settings applied.")

    # ---- thresholds ---------------------------------------------------------------
    def _thresholds(self, tab):
        ctk.CTkLabel(tab, text="Ranges are for SIMULATED data. Outside Normal → warning; outside the critical limits → critical.",
                     text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w", padx=16, pady=(12, 6))
        grid = ctk.CTkFrame(tab, fg_color="transparent")
        grid.pack(anchor="w", padx=16)
        for c, h in enumerate(("Parameter", "Critical below", "Normal min", "Normal max", "Critical above")):
            ctk.CTkLabel(grid, text=h, text_color=COLORS["text_dim"], font=font(10, "bold")).grid(row=0, column=c, padx=6, pady=4, sticky="w")
        self.thr = {}
        for r, p in enumerate(PARAM_KEYS, 1):
            m = REFERENCE_RANGES[p]
            ctk.CTkLabel(grid, text=f'{m["label"]} ({m["unit"]})', font=font(12)).grid(row=r, column=0, sticky="w", padx=6, pady=2)
            es = []
            for c in range(4):
                e = ctk.CTkEntry(grid, width=90, height=28)
                e.grid(row=r, column=c + 1, padx=6, pady=2)
                es.append(e)
            self.thr[p] = es
        self._fill_thr()
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(anchor="w", padx=16, pady=12)
        primary_button(row, "Save thresholds", self.save_thr, 150).pack(side="left", padx=4)
        ghost_button(row, "Reset to defaults", self.reset_thr, 150).pack(side="left", padx=4)

    def _fill_thr(self):
        for p, es in self.thr.items():
            for e, v in zip(es, REFERENCE_RANGES[p]["range"]):
                e.delete(0, "end")
                e.insert(0, str(v))

    def save_thr(self):
        if not self.can("edit_thresholds"):
            return self._deny("authorised staff")
        new = {}
        try:
            for p, es in self.thr.items():
                vals = [validate_float(e.get(), f'{REFERENCE_RANGES[p]["label"]} limit') for e in es]
                if not (vals[0] <= vals[1] < vals[2] <= vals[3]):
                    raise ValidationError(f'{REFERENCE_RANGES[p]["label"]}: need critical-below ≤ min < max ≤ critical-above.')
                new[p] = vals
        except ValidationError as e:
            return error(self, "Thresholds", str(e))
        for p, v in new.items():
            REFERENCE_RANGES[p]["range"] = tuple(v)
        self.app.db.set_json_setting("reference_ranges", new)
        self.app.db.log("INFO", "settings", "Alert thresholds changed", self.app.user["id"])
        info(self, "Thresholds", "Thresholds saved and active immediately.")

    def reset_thr(self):
        if not self.can("edit_thresholds"):
            return self._deny("authorised staff")
        for p in PARAM_KEYS:
            REFERENCE_RANGES[p]["range"] = DEFAULT_RANGES[p]["range"]
        self.app.db.set_json_setting("reference_ranges", {})
        self._fill_thr()

    # ---- users ---------------------------------------------------------------------
    def _users(self, tab):
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=10)
        self.user_btns = []
        for t, c, cls in (("＋ Add user", self.add_user, primary_button), ("Reset password", self.reset_pw, ghost_button),
                          ("Enable / disable", self.toggle_user, ghost_button), ("Delete", self.del_user, danger_button)):
            b = cls(row, t, c, 130)
            b.pack(side="left", padx=3)
            self.user_btns.append(b)
        if not self.can("manage_users"):
            for b in self.user_btns:
                b.configure(state="disabled")
            ctk.CTkLabel(tab, text="User management is restricted to administrators.", text_color=COLORS["warning"]).pack(anchor="w", padx=14)
        self.user_table = DataTable(tab, [("username", "Username", 120), ("full_name", "Name", 200), ("role", "Role", 130),
                                          ("is_active", "Active", 60), ("last_login", "Last login", 140)], height=10, selectmode="browse")
        self.user_table.pack(fill="both", expand=True, padx=10, pady=4)
        self.load_users()

    def load_users(self):
        if self.can("manage_users"):
            rows = self.app.db.list_users()
            for r in rows:
                r["role"] = ROLE_LABELS[r["role"]]
                r["is_active"] = "yes" if r["is_active"] else "no"
            self.user_table.set_rows(rows)

    def add_user(self):
        def save(v):
            self.app.auth.create_user(self.app.user, v["username"], v["password"], next(k for k, l in ROLE_LABELS.items() if l == v["role"]), v["full_name"])
            self.load_users()
        FormDialog(self, "Add user", [{"key": "username", "label": "Username"}, {"key": "full_name", "label": "Full name"},
                                      {"key": "role", "label": "Role", "type": "combo", "values": [ROLE_LABELS[r] for r in ROLES]},
                                      {"key": "password", "label": "Initial password", "type": "password"}], save)

    def _sel_user(self):
        r = self.user_table.selected()
        if not r:
            info(self, "Users", "Select a user first.")
            return None
        return self.app.db.get_user(username=r["username"])

    def reset_pw(self):
        u = self._sel_user()
        if u:
            FormDialog(self, f'Reset password: {u["username"]}', [{"key": "pw", "label": "New password", "type": "password"}],
                       lambda v: self.app.auth.reset_password(self.app.user, u["id"], v["pw"]))

    def toggle_user(self):
        u = self._sel_user()
        if not u:
            return
        if u["id"] == self.app.user["id"]:
            return error(self, "Users", "You cannot disable your own account.")
        self.app.db.update_user(u["id"], is_active=0 if u["is_active"] else 1)
        self.load_users()

    def del_user(self):
        u = self._sel_user()
        if not u:
            return
        if u["id"] == self.app.user["id"]:
            return error(self, "Users", "You cannot delete your own account.")
        admins = [x for x in self.app.db.list_users() if x["role"] == "admin" and x["is_active"]]
        if u["role"] == "admin" and len(admins) <= 1:
            return error(self, "Users", "Cannot delete the last administrator.")
        if confirm(self, "Delete user", f'Delete user "{u["username"]}"?'):
            self.app.db.delete_user(u["id"])
            self.app.db.log("WARNING", "users", f'User {u["username"]} deleted', self.app.user["id"])
            self.load_users()

    # ---- account --------------------------------------------------------------------
    def _account(self, tab):
        u = self.app.user
        ctk.CTkLabel(tab, text=f'Signed in as {u["username"]}  ({ROLE_LABELS[u["role"]]})', font=font(13, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.pw = {}
        for k, label in (("old", "Current password"), ("new", "New password"), ("conf", "Confirm new password")):
            ctk.CTkLabel(tab, text=label, text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w", padx=16)
            e = ctk.CTkEntry(tab, width=260, show="•")
            e.pack(anchor="w", padx=16, pady=(0, 8))
            self.pw[k] = e
        primary_button(tab, "Change password", self.change_pw, 160).pack(anchor="w", padx=16, pady=6)

    def change_pw(self):
        try:
            if self.pw["new"].get() != self.pw["conf"].get():
                raise ValidationError("New password and confirmation do not match.")
            self.app.auth.change_password(self.app.user, self.pw["old"].get(), self.pw["new"].get())
        except ValidationError as e:
            return error(self, "Password", str(e))
        self.app.user = self.app.db.get_user(user_id=self.app.user["id"])
        for e in self.pw.values():
            e.delete(0, "end")
        info(self, "Password", "Password changed.")

    # ---- data & backup ------------------------------------------------------------------
    def _data(self, tab):
        for text, cmd, cls, perm in (("Create backup now", self.backup, primary_button, "backup"),
                                     ("Restore from backup…", self.restore, danger_button, "backup"),
                                     ("Import readings (CSV)…", self.import_csv, ghost_button, "import_data"),
                                     ("Export ALL readings (CSV)", self.export_all, ghost_button, "view_health"),
                                     ("Open backup folder", lambda: open_path(BACKUP_DIR), ghost_button, "view_health")):
            b = cls(tab, text, cmd, 240)
            b.pack(anchor="w", padx=16, pady=6)
            if not self.can(perm):
                b.configure(state="disabled")
        self.data_lbl = ctk.CTkLabel(tab, text="", text_color=COLORS["text_dim"], font=font(11), justify="left")
        self.data_lbl.pack(anchor="w", padx=16, pady=8)
        self.update_backup_label()

    def update_backup_label(self):
        b = backup_service.list_backups()
        self.data_lbl.configure(text=f"{len(b)} backup(s). Latest: {b[0].name if b else 'none'}\nBackups folder: {BACKUP_DIR}")

    def backup(self):
        p = backup_service.create_backup(self.app.db)
        self.update_backup_label()
        info(self, "Backup", f"Backup created:\n{p}")

    def restore(self):
        path = filedialog.askopenfilename(initialdir=str(BACKUP_DIR), filetypes=[("ASTRA-MED backup", "*.db")])
        if not path:
            return
        if not confirm(self, "Restore backup", "This REPLACES all current data with the selected backup (a safety backup is made first). The application will close. Continue?"):
            return
        try:
            safety = backup_service.restore_backup(self.app.db, path)
        except ValueError as e:
            return error(self, "Restore failed", str(e))
        info(self, "Restore complete", f"Data restored. Safety copy of previous data:\n{safety}\n\nPlease start ASTRA-MED again.")
        self.app.restored = True
        self.app.close()

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n, errs = export_service.import_readings_csv(self.app.db, path)
        except Exception as e:
            return error(self, "Import failed", str(e))
        self.app.db.log("INFO", "import", f"Imported {n} readings from {path}", self.app.user["id"])
        info(self, "Import", f"{n} readings imported." + (f"\n{len(errs)} problem(s):\n" + "\n".join(errs[:8]) if errs else ""))

    def export_all(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialdir=str(EXPORT_DIR), initialfile="all_readings.csv")
        if path:
            df = export_service.readings_for_export(self.app.db)
            export_service.export_csv(df, path)
            info(self, "Export", f"{len(df):,} readings exported.")

    # ---- logs ------------------------------------------------------------------------------
    def _logs(self, tab):
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)
        ghost_button(row, "Refresh", self.load_logs, 90).pack(side="left")
        self.log_table = DataTable(tab, [("timestamp", "Time", 140), ("level", "Level", 70), ("source", "Source", 90), ("message", "Message", 520)], height=14)
        self.log_table.pack(fill="both", expand=True, padx=10, pady=4)
        self.load_logs()

    def load_logs(self):
        rows = self.app.db.list_logs(300)
        for r in rows:
            r["sev"] = {"ERROR": "critical", "WARNING": "warning"}.get(r["level"], None)
        self.log_table.set_rows(rows, tag_key="sev")
