import customtkinter as ctk
from config import COLORS
from components.cards import font


class BasePage(ctk.CTkFrame):
    title = "Page"
    subtitle = ""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"], corner_radius=0)
        self.app = app
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(18, 8))
        ctk.CTkLabel(hdr, text=self.title, text_color=COLORS["text"], font=font(22, "bold")).pack(anchor="w")
        if self.subtitle:
            ctk.CTkLabel(hdr, text=self.subtitle, text_color=COLORS["text_dim"], font=font(11)).pack(anchor="w")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=(0, 18))

    def on_show(self):
        """Called when the page becomes visible."""

    def on_telemetry(self, batch):
        """Called for each telemetry batch (GUI thread)."""

    def on_alerts(self, alerts):
        """Called with newly raised alerts (GUI thread)."""

    def can(self, permission):
        from core.authentication import can
        return can(self.app.user, permission)
