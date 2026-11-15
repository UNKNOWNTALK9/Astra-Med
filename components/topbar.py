from datetime import datetime

import customtkinter as ctk

from config import COLORS, ROLE_LABELS, SIMULATION_NOTICE
from components.cards import font, tip
from components.dialogs import confirm


class Topbar(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, height=64, fg_color=COLORS["sidebar"], corner_radius=0)
        self.grid_propagate(False)
        self.app = app
        self.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(self, text="✦ ASTRA-MED", text_color=COLORS["primary"], font=font(14, "bold")).grid(row=0, column=0, padx=(20, 18), pady=18)
        mission = ctk.CTkFrame(self, fg_color="transparent")
        mission.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(mission, text="CURRENT MISSION", text_color=COLORS["text_dim"], font=font(8, "bold")).pack(anchor="w")
        self.mission = ctk.CTkLabel(mission, text="--", text_color=COLORS["text"], font=font(13, "bold"))
        self.mission.pack(anchor="w")
        self.status = ctk.CTkLabel(self, text="", font=font(11, "bold"))
        self.status.grid(row=0, column=2, sticky="w", padx=24)
        ctk.CTkLabel(self, text=SIMULATION_NOTICE, text_color=COLORS["warning"], font=font(9, "bold")).grid(row=0, column=3, padx=12)
        self.clock = ctk.CTkLabel(self, text="", text_color=COLORS["text"], font=font(12))
        self.clock.grid(row=0, column=4, padx=12)
        self.bell = ctk.CTkButton(self, text="🔔 0", width=60, height=32, corner_radius=16, fg_color=COLORS["card"],
                                  hover_color=COLORS["card_hover"], font=font(12), command=lambda: app.show_page("alerts"))
        self.bell.grid(row=0, column=5, padx=6)
        tip(self.bell, "Unacknowledged warning/critical alerts. Click to open.")
        ctk.CTkButton(self, text="⚙", width=34, height=32, corner_radius=16, fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
                      command=lambda: app.show_page("settings")).grid(row=0, column=6, padx=4)
        u = app.user
        ctk.CTkButton(self, text=f'👤 {u["full_name"] or u["username"]} · {ROLE_LABELS[u["role"]]}', height=32, corner_radius=16,
                      fg_color=COLORS["card"], hover_color=COLORS["card_hover"], font=font(12), command=self._logout
                      ).grid(row=0, column=7, padx=(4, 20))
        self._tick()

    def _logout(self):
        if confirm(self, "Sign out", "Sign out of ASTRA-MED?"):
            self.app.logout()

    def _tick(self):
        self.clock.configure(text=datetime.now().strftime("%d %b %Y  %H:%M:%S"))
        self.after(1000, self._tick)

    def set_mission(self, mission):
        if mission:
            self.mission.configure(text=mission["name"])
            self.status.configure(text=f'● MISSION {mission["status"].upper()}', text_color=COLORS["normal"])
        else:
            self.mission.configure(text="No active mission")
            self.status.configure(text="● STANDBY", text_color=COLORS["warning"])

    def set_notifications(self, n):
        self.bell.configure(text=f"🔔 {n}", text_color=COLORS["critical"] if n else COLORS["text"])
