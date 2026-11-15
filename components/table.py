from tkinter import ttk

import customtkinter as ctk

from config import COLORS, FONT_FAMILY, STATUS_COLORS

_styled = False


def _style():
    global _styled
    if _styled:
        return
    st = ttk.Style()
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure("Astra.Treeview", background=COLORS["card"], fieldbackground=COLORS["card"],
                 foreground=COLORS["text"], rowheight=26, borderwidth=0, font=(FONT_FAMILY, 10))
    st.configure("Astra.Treeview.Heading", background=COLORS["sidebar"], foreground=COLORS["text_dim"],
                 relief="flat", font=(FONT_FAMILY, 9, "bold"), borderwidth=0)
    st.map("Astra.Treeview", background=[("selected", "#1E3A5F")], foreground=[("selected", "#FFFFFF")])
    st.map("Astra.Treeview.Heading", background=[("active", COLORS["card_hover"])])
    _styled = True


class DataTable(ctk.CTkFrame):
    """Dark-themed Treeview. columns: list of (key, label, width[, anchor])."""

    def __init__(self, parent, columns, height=12, on_select=None, on_double=None, selectmode="extended"):
        super().__init__(parent, fg_color=COLORS["card"], corner_radius=10, border_width=1,
                         border_color=COLORS["border"])
        _style()
        self.columns = columns
        self.rows = {}
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings", height=height,
                                 style="Astra.Treeview", selectmode=selectmode)
        for c in columns:
            self.tree.heading(c[0], text=c[1])
            self.tree.column(c[0], width=c[2], anchor=c[3] if len(c) > 3 else "w", stretch=True)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="right", fill="y", pady=4)
        for sev, col in STATUS_COLORS.items():
            self.tree.tag_configure(sev, foreground=col)
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(self.selected_rows()))
        if on_double:
            self.tree.bind("<Double-1>", lambda e: on_double(self.selected_rows()))

    def set_rows(self, rows, tag_key=None, fmt=None):
        """rows: list of dicts. tag_key: row key whose value (a severity) colors the row."""
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for i, r in enumerate(rows):
            vals = [(fmt(c[0], r) if fmt else r.get(c[0], "")) for c in self.columns]
            iid = str(i)
            tags = (r.get(tag_key),) if tag_key and r.get(tag_key) in STATUS_COLORS else ()
            self.tree.insert("", "end", iid=iid, values=vals, tags=tags)
            self.rows[iid] = r

    def selected_rows(self):
        return [self.rows[i] for i in self.tree.selection() if i in self.rows]

    def selected(self):
        s = self.selected_rows()
        return s[0] if s else None
