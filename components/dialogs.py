import customtkinter as ctk

from config import COLORS
from components.cards import font, ghost_button, primary_button
from utils.validators import ValidationError

try:
    from CTkMessagebox import CTkMessagebox
except ImportError:  # graceful fallback to native dialogs
    CTkMessagebox = None


def info(parent, title, message):
    if CTkMessagebox:
        CTkMessagebox(title=title, message=message, icon="info").get()
    else:
        from tkinter import messagebox
        messagebox.showinfo(title, message, parent=parent)


def error(parent, title, message):
    if CTkMessagebox:
        CTkMessagebox(title=title, message=message, icon="cancel").get()
    else:
        from tkinter import messagebox
        messagebox.showerror(title, message, parent=parent)


def confirm(parent, title, message) -> bool:
    if CTkMessagebox:
        return CTkMessagebox(title=title, message=message, icon="question",
                             option_1="Cancel", option_2="Confirm").get() == "Confirm"
    from tkinter import messagebox
    return messagebox.askyesno(title, message, parent=parent)


class FormDialog(ctk.CTkToplevel):
    """Generic modal form. fields: dicts with key, label, type (entry|combo|text|password),
    values (combo), default. on_submit(values: dict) may raise ValidationError (shown inline)."""

    def __init__(self, parent, title, fields, on_submit, width=460, submit_text="Save"):
        super().__init__(parent)
        self.title(title)
        self.configure(fg_color=COLORS["card"])
        self.resizable(False, False)
        self.on_submit, self.fields, self.widgets = on_submit, fields, {}
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=22, pady=(18, 6), fill="both")
        for f in fields:
            ctk.CTkLabel(body, text=f["label"], text_color=COLORS["text_dim"], font=font(11),
                         anchor="w").pack(fill="x", pady=(6, 0))
            t = f.get("type", "entry")
            if t == "combo":
                w = ctk.CTkComboBox(body, values=list(f.get("values", [])), width=width - 44, state="readonly",
                                    fg_color=COLORS["bg"], border_color=COLORS["border"])
                w.set(f.get("default") or (f["values"][0] if f.get("values") else ""))
            elif t == "text":
                w = ctk.CTkTextbox(body, width=width - 44, height=80, fg_color=COLORS["bg"],
                                   border_color=COLORS["border"], border_width=1)
                w.insert("1.0", f.get("default", ""))
            else:
                w = ctk.CTkEntry(body, width=width - 44, fg_color=COLORS["bg"], border_color=COLORS["border"],
                                 show="•" if t == "password" else None)
                if f.get("default") not in (None, ""):
                    w.insert(0, str(f["default"]))
                if f.get("readonly"):
                    w.configure(state="disabled")
            w.pack(fill="x")
            self.widgets[f["key"]] = w
        self.err = ctk.CTkLabel(self, text="", text_color=COLORS["critical"], font=font(11), wraplength=width - 44)
        self.err.pack(padx=22, anchor="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=22, pady=(4, 18), anchor="e")
        ghost_button(row, "Cancel", self.destroy, 90).pack(side="left", padx=6)
        primary_button(row, submit_text, self._submit, 110).pack(side="left")
        self.after(120, self._modal)

    def _modal(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def values(self):
        out = {}
        for f in self.fields:
            w = self.widgets[f["key"]]
            out[f["key"]] = w.get("1.0", "end").strip() if f.get("type") == "text" else w.get()
        return out

    def _submit(self):
        try:
            self.on_submit(self.values())
        except ValidationError as e:
            self.err.configure(text=str(e))
            return
        except Exception as e:  # keep the dialog open, show unexpected problems
            self.err.configure(text=f"Error: {e}")
            return
        self.destroy()
