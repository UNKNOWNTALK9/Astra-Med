import customtkinter as ctk
from config import COLORS, STATUS_COLORS, FONT_FAMILY


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


class Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", COLORS["card"])
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", COLORS["border"])
        super().__init__(parent, **kw)


class StatCard(Card):
    """Big-number KPI card."""
    def __init__(self, parent, title, value="--", accent=COLORS["primary"], icon="●"):
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        ctk.CTkLabel(top, text=icon, text_color=accent, font=font(14)).pack(side="left")
        ctk.CTkLabel(top, text=title.upper(), text_color=COLORS["text_dim"],
                     font=font(10, "bold")).pack(side="left", padx=(6, 0))
        self.value_lbl = ctk.CTkLabel(self, text=value, text_color=COLORS["text"],
                                      font=font(26, "bold"), anchor="w")
        self.value_lbl.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 14))

    def set(self, value, color=None):
        self.value_lbl.configure(text=str(value))
        if color:
            self.value_lbl.configure(text_color=color)


class AstronautCard(Card):
    """Compact live-status card for one astronaut."""
    def __init__(self, parent, astronaut, color):
        super().__init__(parent)
        self.astronaut = astronaut
        self.grid_columnconfigure(1, weight=1)
        self.dot = ctk.CTkLabel(self, text="●", text_color=COLORS["normal"], font=font(16))
        self.dot.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=12)
        ctk.CTkLabel(self, text=astronaut["name"], text_color=COLORS["text"],
                     font=font(13, "bold"), anchor="w").grid(row=0, column=1, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(self, text=f'{astronaut["id"]} · {astronaut["role"]}',
                     text_color=COLORS["text_dim"], font=font(10), anchor="w"
                     ).grid(row=1, column=1, sticky="ew", pady=(0, 2))
        self.vitals = ctk.CTkLabel(self, text="♥ --   O₂ --   🌡 --", text_color=color,
                                   font=font(11, "bold"), anchor="w")
        self.vitals.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 6))
        self.badge = ctk.CTkLabel(self, text="NORMAL", text_color=COLORS["normal"],
                                  font=font(9, "bold"))
        self.badge.grid(row=0, column=2, padx=(0, 14), pady=(10, 0))

    def update_reading_status(self, status):
        c = STATUS_COLORS[status]
        self.dot.configure(text_color=c)
        self.badge.configure(text=status.upper(), text_color=c)

    def update_reading(self, reading, status):
        c = STATUS_COLORS[status]
        self.dot.configure(text_color=c)
        self.badge.configure(text=status.upper(), text_color=c)
        self.vitals.configure(
            text=f'♥ {reading["heart_rate"]:.0f}   O₂ {reading["spo2"]:.1f}%   '
                 f'T {reading["temperature"]:.1f}°C')


def primary_button(parent, text, command=None, width=130, **kw):
    kw.setdefault("fg_color", COLORS["primary"])
    kw.setdefault("hover_color", "#0EA5E9")
    kw.setdefault("text_color", "#04111F")
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=32,
                         corner_radius=8, font=font(12, "bold"), **kw)


def ghost_button(parent, text, command=None, width=110, **kw):
    kw.setdefault("fg_color", COLORS["card_hover"])
    kw.setdefault("hover_color", COLORS["border"])
    kw.setdefault("text_color", COLORS["text"])
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=32,
                         corner_radius=8, font=font(12), **kw)


def danger_button(parent, text, command=None, width=110, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=32, corner_radius=8,
                         fg_color="#7F1D1D", hover_color=COLORS["critical"], font=font(12), **kw)


def section_label(parent, text):
    return ctk.CTkLabel(parent, text=text.upper(), text_color=COLORS["text_dim"], font=font(10, "bold"))


def labeled_combo(parent, label, values, width=160, command=None):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=label, text_color=COLORS["text_dim"], font=font(10)).pack(anchor="w")
    cb = ctk.CTkComboBox(f, values=list(values), width=width, height=30, state="readonly",
                         fg_color=COLORS["bg"], border_color=COLORS["border"],
                         button_color=COLORS["border"], command=command)
    if values:
        cb.set(list(values)[0])
    cb.pack()
    return f, cb


def labeled_entry(parent, label, width=130, default="", show=None):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=label, text_color=COLORS["text_dim"], font=font(10)).pack(anchor="w")
    e = ctk.CTkEntry(f, width=width, height=30, fg_color=COLORS["bg"], border_color=COLORS["border"],
                     show=show)
    if default:
        e.insert(0, default)
    e.pack()
    return f, e


def tip(widget, text):
    """Attach a tooltip (CTkToolTip); silently skipped if the package is unavailable."""
    try:
        from CTkToolTip import CTkToolTip
        CTkToolTip(widget, message=text, delay=0.4)
    except Exception:
        pass
