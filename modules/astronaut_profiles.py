import customtkinter as ctk
from config import BLOOD_GROUPS, COLORS
from components.cards import danger_button, font, ghost_button, labeled_combo, primary_button
from components.dialogs import FormDialog, confirm, error, info
from components.table import DataTable
from modules.base_page import BasePage
from utils.validators import (ValidationError, required, validate_age, validate_blood_group, validate_date,
                              validate_phone)
from datetime import datetime


class AstronautProfilesPage(BasePage):
    title = "Astronaut Profiles"
    subtitle = "Manage crew records. Medical history is restricted to Medical Officers."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        self.search = ctk.CTkEntry(bar, placeholder_text="Search name, ID, role, spacecraft…", width=280, height=32,
                                   fg_color=COLORS["card"], border_color=COLORS["border"])
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        f, self.status_cb = labeled_combo(bar, "", ["All statuses", "normal", "warning", "critical"], 130, lambda v: self.refresh())
        f.pack(side="left", padx=8)
        for text, cmd, kind in (("＋ Add", self.add, "p"), ("Edit", self.edit, "g"), ("Delete", self.delete, "d"),
                                ("Health records", self.records, "g"), ("Medical history", self.medical, "g")):
            w = (primary_button if kind == "p" else danger_button if kind == "d" else ghost_button)(bar, text, cmd, 110)
            w.pack(side="right", padx=3)
            if text in ("＋ Add", "Edit", "Delete") and not self.can("manage_astronauts"):
                w.configure(state="disabled")
        self.table = DataTable(self.body, [("code", "ID", 80), ("full_name", "Name", 170), ("age", "Age", 50), ("role", "Role", 140),
                                           ("spacecraft", "Spacecraft", 130), ("missions", "Mission", 150),
                                           ("blood_group", "Blood", 55), ("health_status", "Status", 80),
                                           ("joined_date", "Joined", 90)], height=16,
                               on_double=lambda rows: self.edit(), selectmode="browse")
        self.table.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        st = self.status_cb.get()
        rows = self.app.db.list_astronauts(self.search.get().strip(), "" if st.startswith("All") else st)
        for r in rows:
            r["missions"] = r["missions"] or "-"
            r["blood_group"] = r["blood_group"] or "-"
        self.table.set_rows(rows, tag_key="health_status")

    def on_show(self):
        self.refresh()

    # CRUD 
    def _fields(self, a=None):
        missions = self.app.db.list_missions()
        names = ["(none)"] + [f'{m["code"]} {m["name"]}' for m in missions]
        cur = ""
        if a:
            am = self.app.db.astronaut_missions(a["id"])
            cur = f'{am[0]["code"]} {am[0]["name"]}' if am else "(none)"
        g = lambda k, d="": (a or {}).get(k, d)
        return missions, names, [
            {"key": "code", "label": "Astronaut ID", "default": g("code", self.app.db.next_astronaut_code()), "readonly": True},
            {"key": "full_name", "label": "Full name", "default": g("full_name")},
            {"key": "age", "label": "Age", "default": g("age")},
            {"key": "role", "label": "Mission role", "default": g("role")},
            {"key": "spacecraft", "label": "Assigned spacecraft", "default": g("spacecraft")},
            {"key": "mission", "label": "Mission", "type": "combo", "values": names, "default": cur or "(none)"},
            {"key": "blood_group", "label": "Blood group (optional)", "type": "combo", "values": BLOOD_GROUPS, "default": g("blood_group", "")},
            {"key": "ec_name", "label": "Emergency contact name", "default": g("emergency_contact_name")},
            {"key": "ec_phone", "label": "Emergency contact phone", "default": g("emergency_contact_phone")},
            {"key": "joined_date", "label": "Mission joining date (YYYY-MM-DD)", "default": g("joined_date", datetime.now().strftime("%Y-%m-%d"))},
        ]

    def _save(self, v, a, missions, names):
        data = dict(full_name=required(v["full_name"], "Full name"), age=validate_age(v["age"]),
                    role=v["role"].strip(), spacecraft=v["spacecraft"].strip(),
                    blood_group=validate_blood_group(v["blood_group"]),
                    emergency_contact_name=v["ec_name"].strip(), emergency_contact_phone=validate_phone(v["ec_phone"]),
                    joined_date=validate_date(v["joined_date"], "Joining date"))
        idx = names.index(v["mission"]) if v["mission"] in names else 0
        mid = missions[idx - 1]["id"] if idx > 0 else None
        db = self.app.db
        if a:
            db.update_astronaut(a["id"], **data)
            aid = a["id"]
            db.log("INFO", "profiles", f'Edited astronaut {a["code"]}', self.app.user["id"])
        else:
            aid = db.add_astronaut(code=v["code"], **data)
            db.log("INFO", "profiles", f'Added astronaut {v["code"]}', self.app.user["id"])
        db.set_astronaut_mission(aid, mid)
        self.refresh()
        self.app.refresh_astronauts()

    def add(self):
        if not self.can("manage_astronauts"):
            return error(self, "Not permitted", "Only administrators can add astronauts.")
        missions, names, fields = self._fields()
        FormDialog(self, "Add astronaut", fields, lambda v: self._save(v, None, missions, names))

    def edit(self):
        a = self.table.selected()
        if not a:
            return info(self, "Edit", "Select an astronaut first.")
        if not self.can("manage_astronauts"):
            return error(self, "Not permitted", "Only administrators can edit astronauts.")
        missions, names, fields = self._fields(a)
        FormDialog(self, f'Edit {a["code"]}', fields, lambda v: self._save(v, a, missions, names))

    def delete(self):
        a = self.table.selected()
        if not a:
            return info(self, "Delete", "Select an astronaut first.")
        if not self.can("manage_astronauts"):
            return error(self, "Not permitted", "Only administrators can delete astronauts.")
        if confirm(self, "Delete astronaut", f'Delete {a["full_name"]} and ALL associated readings, alerts and history? This cannot be undone.'):
            self.app.db.delete_astronaut(a["id"])
            self.app.db.log("WARNING", "profiles", f'Deleted astronaut {a["code"]}', self.app.user["id"])
            self.refresh()
            self.app.refresh_astronauts()

    def records(self):
        a = self.table.selected()
        if a:
            self.app.show_page("history", astronaut_code=a["code"])
        else:
            info(self, "Health records", "Select an astronaut first.")

    # restricted medical history 
    def medical(self):
        a = self.table.selected()
        if not a:
            return info(self, "Medical history", "Select an astronaut first.")
        if not self.can("medical_history"):
            self.app.db.log("WARNING", "access", f'Denied medical history access for {a["code"]}', self.app.user["id"])
            return error(self, "Restricted", "Medical history is restricted to Medical Officers.")
        self.app.db.log("INFO", "access", f'Medical history viewed for {a["code"]}', self.app.user["id"])
        MedicalHistoryDialog(self, self.app, a)


class MedicalHistoryDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, astronaut):
        super().__init__(parent)
        self.app, self.a = app, astronaut
        self.title(f'Medical history - {astronaut["full_name"]} (RESTRICTED)')
        self.geometry("720x420")
        self.configure(fg_color=COLORS["card"])
        ctk.CTkLabel(self, text="Confidential clinical information", text_color=COLORS["warning"], font=font(11, "bold")).pack(pady=(12, 4))
        self.table = DataTable(self, [("entry_date", "Date", 90), ("condition", "Condition", 200), ("notes", "Notes", 380)], height=10, selectmode="browse")
        self.table.pack(fill="both", expand=True, padx=12, pady=6)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(0, 12))
        primary_button(row, "＋ Add entry", self.add, 120).pack(side="left", padx=4)
        danger_button(row, "Delete entry", self.delete, 120).pack(side="left", padx=4)
        self.load()

    def load(self):
        self.table.set_rows(self.app.db.list_history(self.a["id"]))

    def add(self):
        def save(v):
            d = validate_date(v["date"], "Date")
            self.app.db.add_history(self.a["id"], d, required(v["cond"], "Condition"), v["notes"], self.app.user["id"])
            self.app.db.log("INFO", "access", f'Medical history entry added for {self.a["code"]}', self.app.user["id"])
            self.load()
        FormDialog(self, "Add medical history entry", [
            {"key": "date", "label": "Date (YYYY-MM-DD)", "default": datetime.now().strftime("%Y-%m-%d")},
            {"key": "cond", "label": "Condition / event"}, {"key": "notes", "label": "Notes", "type": "text"}], save)

    def delete(self):
        r = self.table.selected()
        if r and confirm(self, "Delete entry", "Delete the selected medical history entry?"):
            self.app.db.delete_history(r["id"])
            self.load()
