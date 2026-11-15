import customtkinter as ctk
from config import COLORS, NAV_ITEMS, APP_NAME, TAGLINE
from components.cards import font


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, on_navigate):
        super().__init__(parent, width=240, fg_color=COLORS["sidebar"], corner_radius=0)
        self.grid_propagate(False)
        self.on_navigate = on_navigate
        self.buttons = {}

        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(22, 4))
        ctk.CTkLabel(brand, text="✦", text_color=COLORS["primary"], font=font(26, "bold")).pack(side="left")
        ctk.CTkLabel(brand, text=APP_NAME, text_color=COLORS["text"], font=font(20, "bold")).pack(side="left", padx=8)
        ctk.CTkLabel(self, text=TAGLINE, text_color=COLORS["text_dim"], font=font(9),
                     wraplength=200, justify="left").pack(fill="x", padx=22, pady=(0, 22))

        for key, label, icon in NAV_ITEMS:
            b = ctk.CTkButton(
                self, text=f"  {icon}   {label}", anchor="w", height=42, corner_radius=10,
                fg_color="transparent", hover_color=COLORS["card"], text_color=COLORS["text_dim"],
                font=font(13), command=lambda k=key: self.on_navigate(k))
            b.pack(fill="x", padx=12, pady=2)
            self.buttons[key] = b

        ctk.CTkLabel(self, text="Simulation mode", text_color=COLORS["warning"],
                     font=font(10, "bold")).pack(side="bottom", pady=(0, 16))

    def set_active(self, key):
        for k, b in self.buttons.items():
            active = k == key
            b.configure(fg_color=COLORS["card"] if active else "transparent",
                        text_color=COLORS["primary"] if active else COLORS["text_dim"])
