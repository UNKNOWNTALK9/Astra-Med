from datetime import datetime, timedelta

import customtkinter as ctk

from config import COLORS, MISSION_STATUSES
from components.cards import Card, danger_button, font, ghost_button, primary_button
from components.dialogs import FormDialog, confirm, error, info
from components.table import DataTable
from modules.base_page import BasePage
from utils.validators import ValidationError, required, validate_date

SEV = {"Active": "normal", "Planned": "info", "Completed": "info", "Aborted": "critical"}


def progress(m):
    """Mission progress 0..1 from dates and status."""
    if m["status"] == "Completed":
        return 1.0
    if m["status"] in ("Planned",):
        return 0.0
    try:
        a = datetime.strptime(m["launch_date"], "%Y-%m-%d")
        b = datetime.strptime(m["return_date"], "%Y-%m-%d")
        return min(max((datetime.now() - a) / (b - a), 0.0), 1.0)
    except (ValueError, ZeroDivisionError):
        return 0.0


class MissionManagementPage(BasePage):
    title = "Mission Management"
    subtitle = "Create missions, assign crew and monitor mission progress"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        edit_ok = self.can("manage_missions")
        for text, cmd, cls in (("＋ New mission", self.new, primary_button), ("Edit", self.edit, ghost_button),
                               ("Assign astronauts", self.assign, ghost_button), ("Delete", self.delete, danger_button)):
            w = cls(bar, text, cmd, 140 if "Assign" in text or "New" in text else 90)
            w.pack(side="left", padx=(0, 6))
            if not edit_ok:
                w.configure(state="disabled")
        split = ctk.CTkFrame(self.body, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.grid_columnconfigure(0, weight=3)
        split.grid_columnconfigure(1, weight=2)
        split.grid_rowconfigure(0, weight=1)
        self.table = DataTable(split, [("code", "ID", 70), ("name", "Mission", 160), ("spacecraft", "Spacecraft", 130),
                                       ("launch_date", "Launch", 85), ("return_date", "Return", 85),
                                       ("duration_days", "Days", 50), ("status", "Status", 80),
                                       ("crew_count", "Crew", 45), ("progress", "Progress", 70)],
                               height=16, on_select=lambda rows: self.show_detail(), selectmode="browse")
        self.table.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.detail = Card(split)
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.d_title = ctk.CTkLabel(self.detail, text="Select a mission", text_color=COLORS["text"], font=font(16, "bold"), wraplength=360, justify="left")
        self.d_title.pack(anchor="w", padx=16, pady=(14, 2))
        self.d_meta = ctk.CTkLabel(self.detail, text="", text_color=COLORS["text_dim"], font=font(11), justify="left", wraplength=360)
        self.d_meta.pack(anchor="w", padx=16)
        self.bar = ctk.CTkProgressBar(self.detail, progress_color=COLORS["primary"], fg_color=COLORS["bg"])
        self.bar.set(0)
        self.bar.pack(fill="x", padx=16, pady=10)
        self.d_prog = ctk.CTkLabel(self.detail, text="", text_color=COLORS["text"], font=font(11, "bold"))
        self.d_prog.pack(anchor="w", padx=16)
        self.d_desc = ctk.CTkLabel(self.detail, text="", text_color=COLORS["text"], font=font(11), justify="left", wraplength=360)
        self.d_desc.pack(anchor="w", padx=16, pady=8)
        self.d_crew = ctk.CTkLabel(self.detail, text="", text_color=COLORS["text"], font=font(11), justify="left", wraplength=360)
        self.d_crew.pack(anchor="w", padx=16)
        self.refresh()

    def refresh(self):
        rows = self.app.db.list_missions()
        for m in rows:
            m["progress"] = f"{progress(m) * 100:.0f}%"
            m["sev"] = SEV.get(m["status"], "info")
        self.table.set_rows(rows, tag_key="sev")
        self.show_detail()

    def on_show(self):
        self.refresh()

    def show_detail(self):
        m = self.table.selected()
        if not m:
            return
        p = progress(m)
        crew = self.app.db.mission_crew(m["id"])
        self.d_title.configure(text=f'{m["code"]}  {m["name"]}')
        self.d_meta.configure(text=f'Spacecraft: {m["spacecraft"]}\nLaunch {m["launch_date"]}  →  Return {m["return_date"]}\n'
                                   f'Duration: {m["duration_days"]} days   ·   Status: {m["status"]}')
        self.bar.set(p)
        elapsed = int(p * m["duration_days"])
        self.d_prog.configure(text=f'Progress {p * 100:.0f}%  (day {elapsed} of {m["duration_days"]})')
        self.d_desc.configure(text=m["description"] or "No description.")
        self.d_crew.configure(text="Assigned crew:\n" + ("\n".join(f'  • {c["full_name"]} ({c["role"]})' for c in crew) or "  none"))

    # ---- editing -------------------------------------------------------------
    def _fields(self, m=None):
        g = lambda k, d="": (m or {}).get(k, d)
        today = datetime.now()
        return [{"key": "code", "label": "Mission ID", "default": g("code", self.app.db.next_mission_code()), "readonly": True},
                {"key": "name", "label": "Mission name", "default": g("name")},
                {"key": "spacecraft", "label": "Spacecraft", "default": g("spacecraft")},
                {"key": "launch", "label": "Launch date (YYYY-MM-DD)", "default": g("launch_date", today.strftime("%Y-%m-%d"))},
                {"key": "ret", "label": "Expected return date (YYYY-MM-DD)", "default": g("return_date", (today + timedelta(days=90)).strftime("%Y-%m-%d"))},
                {"key": "status", "label": "Status", "type": "combo", "values": MISSION_STATUSES, "default": g("status", "Planned")},
                {"key": "desc", "label": "Description", "type": "text", "default": g("description")}]

    def _save(self, v, m):
        launch, ret = validate_date(v["launch"], "Launch date"), validate_date(v["ret"], "Return date")
        days = (datetime.strptime(ret, "%Y-%m-%d") - datetime.strptime(launch, "%Y-%m-%d")).days
        if days <= 0:
            raise ValidationError("Return date must be after the launch date.")
        data = dict(name=required(v["name"], "Mission name"), spacecraft=v["spacecraft"].strip(), launch_date=launch,
                    return_date=ret, duration_days=days, status=v["status"], description=v["desc"])
        db = self.app.db
        if m:
            db.update_mission(m["id"], **data)
        else:
            db.add_mission(code=v["code"], **data)
        db.log("INFO", "missions", f'Mission {v["code"]} saved', self.app.user["id"])
        self.refresh()
        self.app.refresh_topbar()

    def new(self):
        FormDialog(self, "New mission", self._fields(), lambda v: self._save(v, None), width=500)

    def edit(self):
        m = self.table.selected()
        if not m:
            return info(self, "Edit", "Select a mission first.")
        FormDialog(self, f'Edit {m["code"]}', self._fields(m), lambda v: self._save(v, m), width=500)

    def delete(self):
        m = self.table.selected()
        if not m:
            return info(self, "Delete", "Select a mission first.")
        if confirm(self, "Delete mission", f'Delete mission "{m["name"]}"? Crew assignments are removed; astronaut records are kept.'):
            self.app.db.delete_mission(m["id"])
            self.refresh()
            self.app.refresh_topbar()

    def assign(self):
        m = self.table.selected()
        if not m:
            return info(self, "Assign", "Select a mission first.")
        AssignDialog(self, self.app, m, self.refresh)


class AssignDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, mission, on_done):
        super().__init__(parent)
        self.app, self.m, self.on_done = app, mission, on_done
        self.title(f'Assign crew - {mission["name"]}')
        self.configure(fg_color=COLORS["card"])
        current = {c["id"] for c in app.db.mission_crew(mission["id"])}
        self.vars = {}
        for a in app.db.list_astronauts(active_only=True):
            cb = ctk.CTkCheckBox(self, text=f'{a["code"]}  {a["full_name"]}  ({a["role"]})', font=font(12))
            if a["id"] in current:
                cb.select()
            cb.pack(anchor="w", padx=22, pady=4)
            self.vars[a["id"]] = cb
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=14)
        ghost_button(row, "Cancel", self.destroy, 90).pack(side="left", padx=6)
        primary_button(row, "Save", self.save, 100).pack(side="left")

    def save(self):
        ids = [i for i, cb in self.vars.items() if cb.get()]
        self.app.db.set_assignments(self.m["id"], ids)
        self.app.db.log("INFO", "missions", f'Crew of {self.m["code"]} set ({len(ids)})', self.app.user["id"])
        self.on_done()
        self.destroy()
