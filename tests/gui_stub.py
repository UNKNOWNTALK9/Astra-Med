"""Headless stand-in for customtkinter/tkinter so page logic can be smoke-tested without a display.
It validates construction, wiring and handlers; it does NOT validate layout or appearance."""
import sys
import types

AFTER_CALLS = []


class W:
    def __init__(self, *a, **k):
        self._text, self._val = "", None
        self._values = list(k.get("values", []))
        self._tabs = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: W()

    def after(self, ms, fn=None, *a):
        AFTER_CALLS.append(fn)
        return "after#"

    def winfo_ismapped(self):
        return True

    def get(self, *a):
        return self._text if self._val is None else self._val

    def insert(self, idx, text, *a):
        self._text = str(text) if self._text == "" else self._text + str(text)

    def delete(self, *a):
        self._text = ""

    def set(self, v):
        self._val = v

    def pack(self, *a, **k):
        pass

    grid = place = pack


class Entry(W):
    def get(self, *a):
        return self._text


class Combo(W):
    def get(self, *a):
        return self._val if self._val is not None else (self._values[0] if self._values else "")


class Check(W):
    def get(self):
        return 1 if self._val else 0

    def select(self):
        self._val = True

    def deselect(self):
        self._val = False


class Slider(W):
    def get(self):
        return self._val if self._val is not None else 0.0


class Tabview(W):
    def add(self, name):
        self._tabs.append(name)
        return W()

    def tab(self, name):
        return W()

    def get(self):
        return self._val or (self._tabs[0] if self._tabs else "")


class Treeview(W):
    def __init__(self, *a, **k):
        super().__init__()
        self._items, self._sel = {}, []

    def insert(self, parent, index, iid=None, values=(), tags=()):
        self._items[iid] = values
        return iid

    def delete(self, *ids):
        self._items.clear()

    def get_children(self):
        return list(self._items)

    def selection(self):
        return self._sel


class Canvas(W):
    def __init__(self, fig=None, master=None):
        super().__init__()

    def get_tk_widget(self):
        return W()


def install(filedialog_path=""):
    ctk = types.ModuleType("customtkinter")
    for n in ("CTk", "CTkToplevel", "CTkFrame", "CTkScrollableFrame", "CTkLabel", "CTkButton", "CTkFont",
              "CTkImage", "CTkProgressBar", "CTkOptionMenu"):
        setattr(ctk, n, type(n, (W,), {}))
    ctk.CTkEntry, ctk.CTkComboBox = Entry, Combo
    ctk.CTkTextbox = type("CTkTextbox", (Entry,), {"get": lambda self, *a: self._text})
    ctk.CTkCheckBox = ctk.CTkSwitch = Check
    ctk.CTkSlider, ctk.CTkTabview = Slider, Tabview
    for f in ("set_appearance_mode", "set_widget_scaling", "set_window_scaling", "set_default_color_theme"):
        setattr(ctk, f, lambda *a, **k: None)
    sys.modules["customtkinter"] = ctk

    tk = types.ModuleType("tkinter")
    ttk = types.ModuleType("tkinter.ttk")
    ttk.Treeview, ttk.Style, ttk.Scrollbar = Treeview, W, W
    fd = types.ModuleType("tkinter.filedialog")
    fd.asksaveasfilename = lambda **k: filedialog_path + k.get("defaultextension", ".csv")
    fd.askopenfilename = lambda **k: filedialog_path
    mb = types.ModuleType("tkinter.messagebox")
    mb.showinfo = mb.showerror = lambda *a, **k: True
    mb.askyesno = lambda *a, **k: True
    tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.filedialog": fd, "tkinter.messagebox": mb})

    import matplotlib
    matplotlib.use = lambda *a, **k: None
    bt = types.ModuleType("matplotlib.backends.backend_tkagg")
    bt.FigureCanvasTkAgg, bt.NavigationToolbar2Tk = Canvas, W
    sys.modules["matplotlib.backends.backend_tkagg"] = bt
    return fd
