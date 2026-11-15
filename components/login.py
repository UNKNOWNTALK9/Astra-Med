import customtkinter as ctk
from PIL import Image

from config import APP_NAME, COLORS, TAGLINE, VERSION
from components.cards import font, primary_button
from core.authentication import AuthService
from utils.helpers import ensure_logo


class LoginWindow(ctk.CTk):
    def __init__(self, db):
        super().__init__()
        self.db, self.auth, self.user = db, AuthService(db), None
        self.title(f"{APP_NAME} - Sign in")
        self.geometry("420x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        card = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=18, border_width=1, border_color=COLORS["border"])
        card.pack(expand=True, fill="both", padx=24, pady=24)
        try:
            img = ctk.CTkImage(Image.open(ensure_logo()), size=(84, 84))
            ctk.CTkLabel(card, image=img, text="").pack(pady=(26, 6))
        except Exception:
            ctk.CTkLabel(card, text="✦", text_color=COLORS["primary"], font=font(44)).pack(pady=(26, 6))
        ctk.CTkLabel(card, text=APP_NAME, text_color=COLORS["text"], font=font(26, "bold")).pack()
        ctk.CTkLabel(card, text="Astronaut Health Monitoring &\nMission Control System", text_color=COLORS["text_dim"], font=font(11)).pack()
        ctk.CTkLabel(card, text=TAGLINE, text_color=COLORS["primary"], font=font(10)).pack(pady=(4, 18))
        self.user_e = ctk.CTkEntry(card, placeholder_text="Username", width=280, height=38, fg_color=COLORS["bg"], border_color=COLORS["border"])
        self.user_e.pack(pady=6)
        self.pw_e = ctk.CTkEntry(card, placeholder_text="Password", show="•", width=280, height=38, fg_color=COLORS["bg"], border_color=COLORS["border"])
        self.pw_e.pack(pady=6)
        self.msg = ctk.CTkLabel(card, text="", text_color=COLORS["critical"], font=font(11), wraplength=280)
        self.msg.pack(pady=4)
        primary_button(card, "Sign in", self.submit, 280, ).pack(pady=6)
        ctk.CTkLabel(card, text="All data in this application is SIMULATED.\nDemo accounts are listed in the README.",
                     text_color=COLORS["warning"], font=font(10)).pack(pady=(14, 0))
        ctk.CTkLabel(card, text=f"v{VERSION}", text_color=COLORS["text_dim"], font=font(9)).pack(side="bottom", pady=8)
        self.bind("<Return>", lambda e: self.submit())
        self.user_e.focus_set()

    def submit(self):
        user, msg = self.auth.login(self.user_e.get(), self.pw_e.get())
        if user:
            self.user = user
            self.destroy()
        else:
            self.msg.configure(text=msg)
            self.pw_e.delete(0, "end")

    def run(self):
        self.mainloop()
        return self.user
