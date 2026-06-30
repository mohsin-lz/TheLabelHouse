"""
Label Printer Pro
=================
A professional label design and printing tool.
Supports drag & drop elements, text editing, images, and custom label sizes.
Default: 4x6 inch (100x150mm) thermal labels — common Amazon India shipping label size.

Requirements:
    pip install pillow reportlab

To build .exe on Windows:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "LabelPrinterPro" label_printer.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font as tkfont
import math
import json
import os
import copy
import win32print
from datetime import datetime

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm, inch
    from reportlab.lib.pagesizes import landscape
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ─────────────────────────────────────────────
#  Constants & Label Presets
# ─────────────────────────────────────────────

LABEL_PRESETS = {
    "4×6 inch – Shipping (Amazon/Flipkart)": (4.0, 6.0),
    "4×4 inch – Square Label":               (4.0, 4.0),
    "3×2 inch – Small Product":              (3.0, 2.0),
    "2×1 inch – Barcode/Price Tag":          (2.0, 1.0),
    "3.5×1 inch – File/Box Label":           (3.5, 1.0),
    "A4 Full Page":                          (8.27, 11.69),
    "TCS Label 01":                          (3.25, 1.00),
    "Custom…":                               None,
}

DPI = 96          # screen DPI for canvas preview
CANVAS_SCALE = 2  # multiply label inches → canvas pixels (96 DPI * 2 = 192 px/inch preview)
MARGIN = 30       # canvas margin in pixels

APP_BG   = "#1e1e2e"
PANEL_BG = "#2a2a3e"
BTN_BG   = "#4a4af0"
BTN_HOV  = "#6060ff"
ACCENT   = "#7c7cff"
TEXT_COL = "#e0e0f0"
CANVAS_BG= "#ffffff"
HANDLE_COL = "#4a4af0"
SEL_COL  = "#4a4af0"

# ─────────────────────────────────────────────
#  Element Classes
# ─────────────────────────────────────────────

class LabelElement:
    _id_counter = 0

    def __init__(self, kind, x, y):
        LabelElement._id_counter += 1
        self.id   = LabelElement._id_counter
        self.kind = kind   # "text" | "image" | "rect" | "line" | "barcode"
        self.x    = x      # inches from top-left
        self.y    = y
        self.selected = False

    def to_dict(self):
        return {"kind": self.kind, "x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, d):
        raise NotImplementedError


class TextElement(LabelElement):
    def __init__(self, x=0.1, y=0.1, text="Text", font_name="Arial",
                 font_size=18, bold=False, italic=False, color="#000000",
                 align="left", rotation=0, width=None, height=None):
        super().__init__("text", x, y)
        self.text      = text
        self.font_name = font_name
        self.font_size = font_size
        self.bold      = bold
        self.italic    = italic
        self.color     = color
        self.align     = align      # left / center / right
        self.rotation  = rotation  # degrees
        self.width     = width  or 2.0
        self.height    = height or 0.4

    def to_dict(self):
        d = super().to_dict()
        d.update(text=self.text, font_name=self.font_name, font_size=self.font_size,
                 bold=self.bold, italic=self.italic, color=self.color,
                 align=self.align, rotation=self.rotation,
                 width=self.width, height=self.height)
        return d

    @classmethod
    def from_dict(cls, d):
        e = cls(d["x"], d["y"], d["text"], d["font_name"], d["font_size"],
                d["bold"], d["italic"], d["color"], d.get("align","left"),
                d.get("rotation",0), d.get("width",2.0), d.get("height",0.4))
        return e


class ImageElement(LabelElement):
    def __init__(self, x=0.1, y=0.1, path="", width=1.5, height=1.5):
        super().__init__("image", x, y)
        self.path   = path
        self.width  = width
        self.height = height

    def to_dict(self):
        d = super().to_dict()
        d.update(path=self.path, width=self.width, height=self.height)
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d["x"], d["y"], d["path"], d["width"], d["height"])


class RectElement(LabelElement):
    def __init__(self, x=0.1, y=0.1, width=1.0, height=0.5,
                 fill="#ffffff", stroke="#000000", stroke_width=1, radius=0):
        super().__init__("rect", x, y)
        self.width        = width
        self.height       = height
        self.fill         = fill
        self.stroke       = stroke
        self.stroke_width = stroke_width
        self.radius       = radius  # rounded corners (px)

    def to_dict(self):
        d = super().to_dict()
        d.update(width=self.width, height=self.height, fill=self.fill,
                 stroke=self.stroke, stroke_width=self.stroke_width, radius=self.radius)
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d["x"], d["y"], d["width"], d["height"],
                   d.get("fill","#ffffff"), d.get("stroke","#000000"),
                   d.get("stroke_width",1), d.get("radius",0))


# ─────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────

class LabelPrinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Label Printer Pro")
        self.geometry("1280x820")
        self.configure(bg=APP_BG)
        self.resizable(True, True)

        # State
        self.label_w   = 4.0   # inches
        self.label_h   = 6.0
        self.elements  = []    # list of LabelElement
        self.selected  = None  # currently selected element
        self.clipboard = None

        self._drag_data   = {}   # for element dragging
        self._resize_data = {}
        self._undo_stack  = []
        self._redo_stack  = []

        # Image cache (element.id → PhotoImage)
        self._img_cache = {}

        self._build_ui()
        self._bind_shortcuts()
        self._push_undo()
        self._refresh_canvas()

    # ══════════════════════════════════════════
    #  UI Construction
    # ══════════════════════════════════════════

    def _build_ui(self):
        # ── Top menu bar ──
        self._build_menubar()

        # ── Main layout: left toolbar | canvas | right properties ──
        main = tk.Frame(self, bg=APP_BG)
        main.pack(fill="both", expand=True)

        self._build_toolbar(main)
        self._build_canvas_area(main)
        self._build_properties(main)

    def _build_menubar(self):
        mb = tk.Menu(self, bg=PANEL_BG, fg=TEXT_COL, activebackground=ACCENT,
                     activeforeground="white", tearoff=False)
        self.config(menu=mb)

        # File
        fm = tk.Menu(mb, bg=PANEL_BG, fg=TEXT_COL, activebackground=ACCENT,
                     activeforeground="white", tearoff=False)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="New Label",      command=self._new_label,   accelerator="Ctrl+N")
        fm.add_command(label="Open…",          command=self._open_file,   accelerator="Ctrl+O")
        fm.add_command(label="Save…",          command=self._save_file,   accelerator="Ctrl+S")
        fm.add_separator()
        fm.add_command(label="Export PDF…",    command=self._export_pdf,  accelerator="Ctrl+E")
        fm.add_command(label="Export PNG…",    command=self._export_png,  accelerator="Ctrl+Shift+E")
        fm.add_separator()
        fm.add_command(label="Print…",         command=self._print_label, accelerator="Ctrl+P")
        fm.add_separator()
        fm.add_command(label="Exit",           command=self.quit)

        # Edit
        em = tk.Menu(mb, bg=PANEL_BG, fg=TEXT_COL, activebackground=ACCENT,
                     activeforeground="white", tearoff=False)
        mb.add_cascade(label="Edit", menu=em)
        em.add_command(label="Undo",     command=self._undo, accelerator="Ctrl+Z")
        em.add_command(label="Redo",     command=self._redo, accelerator="Ctrl+Y")
        em.add_separator()
        em.add_command(label="Copy",     command=self._copy,   accelerator="Ctrl+C")
        em.add_command(label="Paste",    command=self._paste,  accelerator="Ctrl+V")
        em.add_command(label="Delete",   command=self._delete, accelerator="Delete")
        em.add_separator()
        em.add_command(label="Select All", command=self._select_all, accelerator="Ctrl+A")

        # Label
        lm = tk.Menu(mb, bg=PANEL_BG, fg=TEXT_COL, activebackground=ACCENT,
                     activeforeground="white", tearoff=False)
        mb.add_cascade(label="Label", menu=lm)
        lm.add_command(label="Label Size / Settings…", command=self._label_settings)

    def _build_toolbar(self, parent):
        tb = tk.Frame(parent, bg=PANEL_BG, width=64, padx=6, pady=6)
        tb.pack(side="left", fill="y")
        tb.pack_propagate(False)

        def tool_btn(text, cmd, tip=""):
            btn = tk.Button(tb, text=text, command=cmd, bg=BTN_BG, fg="white",
                            relief="flat", padx=4, pady=8, font=("Arial", 9, "bold"),
                            cursor="hand2", width=5, activebackground=BTN_HOV,
                            activeforeground="white")
            btn.pack(fill="x", pady=3)
            return btn

        tk.Label(tb, text="ADD", bg=PANEL_BG, fg=ACCENT,
                 font=("Arial", 8, "bold")).pack(pady=(4,2))

        tool_btn("🔤 Text",  self._add_text,  "Add text element")
        tool_btn("🖼 Image", self._add_image, "Add image element")
        tool_btn("▭ Rect",  self._add_rect,  "Add rectangle")

        ttk.Separator(tb, orient="horizontal").pack(fill="x", pady=8)
        tk.Label(tb, text="ALIGN", bg=PANEL_BG, fg=ACCENT,
                 font=("Arial", 8, "bold")).pack(pady=(0,2))

        tool_btn("⇐ Left",   lambda: self._align("left"))
        tool_btn("⇔ Center", lambda: self._align("center_h"))
        tool_btn("⇒ Right",  lambda: self._align("right"))
        tool_btn("⇑ Top",    lambda: self._align("top"))
        tool_btn("⇕ Mid",    lambda: self._align("center_v"))
        tool_btn("⇓ Bottom", lambda: self._align("bottom"))

        ttk.Separator(tb, orient="horizontal").pack(fill="x", pady=8)
        tk.Label(tb, text="LAYER", bg=PANEL_BG, fg=ACCENT,
                 font=("Arial", 8, "bold")).pack(pady=(0,2))

        tool_btn("↑ Fwd",  self._bring_forward)
        tool_btn("↓ Back", self._send_backward)

    def _build_canvas_area(self, parent):
        area = tk.Frame(parent, bg=APP_BG)
        area.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        # Label size selector row
        top = tk.Frame(area, bg=APP_BG)
        top.pack(fill="x", pady=(0, 6))

        tk.Label(top, text="Label Size:", bg=APP_BG, fg=TEXT_COL,
                 font=("Arial", 10)).pack(side="left")

        self._preset_var = tk.StringVar(value="4×6 inch – Shipping (Amazon/Flipkart)")
        combo = ttk.Combobox(top, textvariable=self._preset_var,
                             values=list(LABEL_PRESETS.keys()), width=34,
                             state="readonly")
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", self._on_preset_change)

        tk.Label(top, text="W:", bg=APP_BG, fg=TEXT_COL).pack(side="left", padx=(10,2))
        self._w_var = tk.DoubleVar(value=4.0)
        tk.Spinbox(top, textvariable=self._w_var, from_=0.5, to=20.0,
                   increment=0.1, width=5, format="%.2f",
                   command=self._on_size_change).pack(side="left")

        tk.Label(top, text="H:", bg=APP_BG, fg=TEXT_COL).pack(side="left", padx=(6,2))
        self._h_var = tk.DoubleVar(value=6.0)
        tk.Spinbox(top, textvariable=self._h_var, from_=0.5, to=20.0,
                   increment=0.1, width=5, format="%.2f",
                   command=self._on_size_change).pack(side="left")

        tk.Label(top, text="inches", bg=APP_BG, fg=TEXT_COL).pack(side="left", padx=4)

        # Zoom
        tk.Label(top, text="Zoom:", bg=APP_BG, fg=TEXT_COL).pack(side="left", padx=(16,2))
        self._zoom_var = tk.IntVar(value=100)
        zoom_cb = ttk.Combobox(top, textvariable=self._zoom_var,
                               values=[50,75,100,125,150,200], width=5)
        zoom_cb.pack(side="left")
        zoom_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_canvas())

        tk.Label(top, text="%", bg=APP_BG, fg=TEXT_COL).pack(side="left", padx=2)

        # Print button in toolbar row
        tk.Button(top, text="🖨 PRINT", command=self._print_label,
                  bg="#22bb55", fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  activebackground="#19a044").pack(side="right", padx=4)

        tk.Button(top, text="📄 Export PDF", command=self._export_pdf,
                  bg="#e67e22", fg="white", font=("Arial", 10, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground="#d35400").pack(side="right", padx=4)

        # Canvas with scrollbars
        canvas_frame = tk.Frame(area, bg="#333355")
        canvas_frame.pack(fill="both", expand=True)

        self._hscroll = ttk.Scrollbar(canvas_frame, orient="horizontal")
        self._hscroll.pack(side="bottom", fill="x")
        self._vscroll = ttk.Scrollbar(canvas_frame, orient="vertical")
        self._vscroll.pack(side="right", fill="y")

        self._canvas = tk.Canvas(canvas_frame, bg="#4a4a6a",
                                 xscrollcommand=self._hscroll.set,
                                 yscrollcommand=self._vscroll.set,
                                 cursor="crosshair")
        self._canvas.pack(fill="both", expand=True)
        self._hscroll.config(command=self._canvas.xview)
        self._vscroll.config(command=self._canvas.yview)

        # Canvas bindings
        self._canvas.bind("<ButtonPress-1>",   self._on_canvas_press)
        self._canvas.bind("<B1-Motion>",       self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self._canvas.bind("<Double-Button-1>", self._on_canvas_dblclick)
        self._canvas.bind("<Button-3>",        self._on_canvas_rclick)

        # Status bar
        self._status = tk.StringVar(value="Ready  |  Label: 4.00 × 6.00 in")
        tk.Label(area, textvariable=self._status, bg="#111122", fg="#88aabb",
                 font=("Arial", 9), anchor="w", padx=6).pack(fill="x")

    def _build_properties(self, parent):
        pf = tk.Frame(parent, bg=PANEL_BG, width=240)
        pf.pack(side="right", fill="y", padx=(0,0))
        pf.pack_propagate(False)

        tk.Label(pf, text="PROPERTIES", bg=PANEL_BG, fg=ACCENT,
                 font=("Arial", 10, "bold"), pady=8).pack(fill="x")

        self._prop_frame = tk.Frame(pf, bg=PANEL_BG)
        self._prop_frame.pack(fill="both", expand=True, padx=8)

        self._show_no_selection()

    def _show_no_selection(self):
        for w in self._prop_frame.winfo_children():
            w.destroy()
        tk.Label(self._prop_frame, text="Select an element\nto edit its properties",
                 bg=PANEL_BG, fg="#888899", justify="center",
                 font=("Arial", 10)).pack(pady=30)

    def _show_text_properties(self, el: TextElement):
        f = self._prop_frame
        for w in f.winfo_children():
            w.destroy()

        def lbl(t):
            tk.Label(f, text=t, bg=PANEL_BG, fg=TEXT_COL,
                     font=("Arial", 9), anchor="w").pack(fill="x", pady=(6,0))

        def row():
            r = tk.Frame(f, bg=PANEL_BG)
            r.pack(fill="x", pady=1)
            return r

        # Text content
        lbl("Text Content:")
        self._txt_var = tk.StringVar(value=el.text)
        txt_entry = tk.Text(f, height=3, font=("Arial", 10), bg="#333350",
                            fg=TEXT_COL, insertbackground="white",
                            relief="flat", padx=4, pady=4)
        txt_entry.insert("1.0", el.text)
        txt_entry.pack(fill="x", pady=2)

        def on_text_change(event=None):
            el.text = txt_entry.get("1.0", "end-1c")
            self._refresh_canvas()
        txt_entry.bind("<KeyRelease>", on_text_change)

        # Font family
        lbl("Font:")
        fonts = sorted(set(tkfont.families()))[:100]
        self._font_var = tk.StringVar(value=el.font_name)
        font_cb = ttk.Combobox(f, textvariable=self._font_var, values=fonts,
                               state="readonly", width=20)
        font_cb.pack(fill="x", pady=1)
        def on_font(e):
            el.font_name = self._font_var.get()
            self._refresh_canvas()
        font_cb.bind("<<ComboboxSelected>>", on_font)

        # Font size
        r = row()
        tk.Label(r, text="Size:", bg=PANEL_BG, fg=TEXT_COL, width=6).pack(side="left")
        self._fsize_var = tk.IntVar(value=el.font_size)
        sp = tk.Spinbox(r, textvariable=self._fsize_var, from_=4, to=200,
                        width=6, bg="#333350", fg=TEXT_COL,
                        buttonbackground=PANEL_BG)
        sp.pack(side="left")
        def on_size(*a):
            try:
                el.font_size = int(self._fsize_var.get())
                self._refresh_canvas()
            except: pass
        self._fsize_var.trace_add("write", on_size)

        # Bold / Italic
        r2 = row()
        self._bold_var = tk.BooleanVar(value=el.bold)
        tk.Checkbutton(r2, text="Bold", variable=self._bold_var, bg=PANEL_BG,
                       fg=TEXT_COL, selectcolor="#333350",
                       command=lambda: [setattr(el, "bold", self._bold_var.get()),
                                        self._refresh_canvas()]).pack(side="left")
        self._italic_var = tk.BooleanVar(value=el.italic)
        tk.Checkbutton(r2, text="Italic", variable=self._italic_var, bg=PANEL_BG,
                       fg=TEXT_COL, selectcolor="#333350",
                       command=lambda: [setattr(el, "italic", self._italic_var.get()),
                                        self._refresh_canvas()]).pack(side="left")

        # Color
        lbl("Color:")
        self._color_frame = tk.Frame(f, bg=el.color, width=30, height=22)
        self._color_frame.pack(fill="x", pady=2)
        def pick_color():
            c = colorchooser.askcolor(color=el.color, title="Text Color")
            if c[1]:
                el.color = c[1]
                self._color_frame.configure(bg=el.color)
                self._refresh_canvas()
        tk.Button(f, text="Choose Color…", command=pick_color,
                  bg="#333350", fg=TEXT_COL, relief="flat").pack(fill="x", pady=2)

        # Alignment
        lbl("Alignment:")
        r3 = row()
        self._align_var = tk.StringVar(value=el.align)
        for a in ["left","center","right"]:
            tk.Radiobutton(r3, text=a.title(), variable=self._align_var,
                           value=a, bg=PANEL_BG, fg=TEXT_COL,
                           selectcolor="#333350",
                           command=lambda: [setattr(el, "align", self._align_var.get()),
                                            self._refresh_canvas()]).pack(side="left")

        # Position & Size
        lbl("Position (inches):")
        r4 = row()
        tk.Label(r4, text="X:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        xv = tk.DoubleVar(value=round(el.x,3))
        tk.Spinbox(r4, textvariable=xv, from_=-10, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"x",xv.get()), self._refresh_canvas()]
                   ).pack(side="left")
        tk.Label(r4, text="Y:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        yv = tk.DoubleVar(value=round(el.y,3))
        tk.Spinbox(r4, textvariable=yv, from_=-10, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"y",yv.get()), self._refresh_canvas()]
                   ).pack(side="left")

        lbl("Size (inches):")
        r5 = row()
        tk.Label(r5, text="W:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        wv = tk.DoubleVar(value=round(el.width,3))
        tk.Spinbox(r5, textvariable=wv, from_=0.1, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"width",wv.get()), self._refresh_canvas()]
                   ).pack(side="left")
        tk.Label(r5, text="H:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        hv = tk.DoubleVar(value=round(el.height,3))
        tk.Spinbox(r5, textvariable=hv, from_=0.1, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"height",hv.get()), self._refresh_canvas()]
                   ).pack(side="left")

        # Delete button
        tk.Button(f, text="🗑 Delete Element", command=self._delete,
                  bg="#cc3333", fg="white", relief="flat", pady=4,
                  cursor="hand2").pack(fill="x", pady=(16,4))

    def _show_rect_properties(self, el: RectElement):
        f = self._prop_frame
        for w in f.winfo_children():
            w.destroy()

        def lbl(t):
            tk.Label(f, text=t, bg=PANEL_BG, fg=TEXT_COL,
                     font=("Arial", 9), anchor="w").pack(fill="x", pady=(6,0))

        def row():
            r = tk.Frame(f, bg=PANEL_BG); r.pack(fill="x", pady=1); return r

        lbl("Fill Color:")
        fc = tk.Frame(f, bg=el.fill, height=22)
        fc.pack(fill="x", pady=2)
        def pick_fill():
            c = colorchooser.askcolor(color=el.fill, title="Fill Color")
            if c[1]:
                el.fill = c[1]; fc.configure(bg=el.fill); self._refresh_canvas()
        tk.Button(f, text="Choose Fill…", command=pick_fill,
                  bg="#333350", fg=TEXT_COL, relief="flat").pack(fill="x", pady=2)

        lbl("Stroke Color:")
        sc = tk.Frame(f, bg=el.stroke, height=22)
        sc.pack(fill="x", pady=2)
        def pick_stroke():
            c = colorchooser.askcolor(color=el.stroke, title="Stroke Color")
            if c[1]:
                el.stroke = c[1]; sc.configure(bg=el.stroke); self._refresh_canvas()
        tk.Button(f, text="Choose Stroke…", command=pick_stroke,
                  bg="#333350", fg=TEXT_COL, relief="flat").pack(fill="x", pady=2)

        lbl("Stroke Width (px):")
        swv = tk.IntVar(value=el.stroke_width)
        tk.Spinbox(f, textvariable=swv, from_=0, to=20, width=6,
                   bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"stroke_width",swv.get()),
                                    self._refresh_canvas()]).pack(fill="x")

        lbl("Position (inches):")
        r4 = row()
        xv = tk.DoubleVar(value=round(el.x,3))
        tk.Label(r4, text="X:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        tk.Spinbox(r4, textvariable=xv, from_=-10, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"x",xv.get()), self._refresh_canvas()]).pack(side="left")
        tk.Label(r4, text="Y:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        yv = tk.DoubleVar(value=round(el.y,3))
        tk.Spinbox(r4, textvariable=yv, from_=-10, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"y",yv.get()), self._refresh_canvas()]).pack(side="left")

        lbl("Size (inches):")
        r5 = row()
        wv = tk.DoubleVar(value=round(el.width,3))
        tk.Label(r5, text="W:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        tk.Spinbox(r5, textvariable=wv, from_=0.1, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"width",wv.get()), self._refresh_canvas()]).pack(side="left")
        tk.Label(r5, text="H:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        hv = tk.DoubleVar(value=round(el.height,3))
        tk.Spinbox(r5, textvariable=hv, from_=0.1, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"height",hv.get()), self._refresh_canvas()]).pack(side="left")

        tk.Button(f, text="🗑 Delete Element", command=self._delete,
                  bg="#cc3333", fg="white", relief="flat", pady=4,
                  cursor="hand2").pack(fill="x", pady=(16,4))

    def _show_image_properties(self, el: ImageElement):
        f = self._prop_frame
        for w in f.winfo_children():
            w.destroy()

        def lbl(t):
            tk.Label(f, text=t, bg=PANEL_BG, fg=TEXT_COL,
                     font=("Arial", 9), anchor="w").pack(fill="x", pady=(6,0))
        def row():
            r = tk.Frame(f, bg=PANEL_BG); r.pack(fill="x", pady=1); return r

        lbl("Image Path:")
        tk.Label(f, text=os.path.basename(el.path) or "(none)", bg=PANEL_BG,
                 fg=ACCENT, wraplength=200).pack(fill="x")

        def change_img():
            p = filedialog.askopenfilename(
                title="Choose Image",
                filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.gif *.tif *.webp"),
                           ("All","*.*")])
            if p:
                el.path = p
                self._img_cache.pop(el.id, None)
                self._refresh_canvas()
                self._show_image_properties(el)
        tk.Button(f, text="Change Image…", command=change_img,
                  bg="#333350", fg=TEXT_COL, relief="flat").pack(fill="x", pady=4)

        lbl("Size (inches):")
        r5 = row()
        wv = tk.DoubleVar(value=round(el.width,3))
        tk.Label(r5, text="W:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        tk.Spinbox(r5, textvariable=wv, from_=0.1, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"width",wv.get()), self._refresh_canvas()]).pack(side="left")
        tk.Label(r5, text="H:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        hv = tk.DoubleVar(value=round(el.height,3))
        tk.Spinbox(r5, textvariable=hv, from_=0.1, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"height",hv.get()), self._refresh_canvas()]).pack(side="left")

        lbl("Position (inches):")
        r4 = row()
        xv = tk.DoubleVar(value=round(el.x,3))
        tk.Label(r4, text="X:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        tk.Spinbox(r4, textvariable=xv, from_=-10, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"x",xv.get()), self._refresh_canvas()]).pack(side="left")
        tk.Label(r4, text="Y:", bg=PANEL_BG, fg=TEXT_COL, width=3).pack(side="left")
        yv = tk.DoubleVar(value=round(el.y,3))
        tk.Spinbox(r4, textvariable=yv, from_=-10, to=20, increment=0.05,
                   width=6, format="%.3f", bg="#333350", fg=TEXT_COL,
                   command=lambda: [setattr(el,"y",yv.get()), self._refresh_canvas()]).pack(side="left")

        tk.Button(f, text="🗑 Delete Element", command=self._delete,
                  bg="#cc3333", fg="white", relief="flat", pady=4,
                  cursor="hand2").pack(fill="x", pady=(16,4))

    # ══════════════════════════════════════════
    #  Canvas Drawing
    # ══════════════════════════════════════════

    def _scale(self):
        zoom = self._zoom_var.get() / 100.0
        return DPI * zoom  # px per inch on canvas

    def _to_canvas(self, ix, iy):
        """Convert label inches → canvas pixels"""
        s = self._scale()
        return MARGIN + ix * s, MARGIN + iy * s

    def _to_label(self, cx, cy):
        """Convert canvas pixels → label inches"""
        s = self._scale()
        return (cx - MARGIN) / s, (cy - MARGIN) / s

    def _canvas_w(self):
        return int(MARGIN * 2 + self.label_w * self._scale())

    def _canvas_h(self):
        return int(MARGIN * 2 + self.label_h * self._scale())

    def _refresh_canvas(self):
        c = self._canvas
        c.delete("all")
        s = self._scale()
        cw = self._canvas_w()
        ch = self._canvas_h()

        # Scroll region
        c.configure(scrollregion=(0, 0, cw + 20, ch + 20))

        # Shadow
        c.create_rectangle(MARGIN + 4, MARGIN + 4, cw - MARGIN + 4, ch - MARGIN + 4,
                            fill="#000000", outline="", stipple="gray25")
        # White label area
        c.create_rectangle(MARGIN, MARGIN, cw - MARGIN, ch - MARGIN,
                            fill="white", outline="#888888", width=1)

        # Grid (light)
        for xi in range(0, int(self.label_w * 10) + 1):
            x = MARGIN + xi * s / 10
            col = "#ddddee" if xi % 10 != 0 else "#bbbbcc"
            c.create_line(x, MARGIN, x, ch - MARGIN, fill=col, width=1 if xi%10 else 1)
        for yi in range(0, int(self.label_h * 10) + 1):
            y = MARGIN + yi * s / 10
            col = "#ddddee" if yi % 10 != 0 else "#bbbbcc"
            c.create_line(MARGIN, y, cw - MARGIN, y, fill=col, width=1 if yi%10 else 1)

        # Elements (back to front)
        for el in self.elements:
            self._draw_element(c, el, s)

        # Status
        sel_info = ""
        if self.selected:
            el = self.selected
            sel_info = f"  |  {el.kind.title()} @ ({el.x:.2f}\", {el.y:.2f}\")"
        self._status.set(f"Label: {self.label_w:.2f}\" × {self.label_h:.2f}\"  "
                         f"|  Elements: {len(self.elements)}{sel_info}")

    def _draw_element(self, c, el, s):
        x0, y0 = self._to_canvas(el.x, el.y)

        if isinstance(el, RectElement):
            x1, y1 = self._to_canvas(el.x + el.width, el.y + el.height)
            fill = el.fill if el.fill != "none" else ""
            c.create_rectangle(x0, y0, x1, y1, fill=fill,
                                outline=el.stroke, width=el.stroke_width)

        elif isinstance(el, TextElement):
            x1, y1 = self._to_canvas(el.x + el.width, el.y + el.height)
            # Clipping via a rectangle tag – we'll just draw text in a box
            style = ""
            if el.bold and el.italic:
                style = "bold italic"
            elif el.bold:
                style = "bold"
            elif el.italic:
                style = "italic"

            size_px = max(6, int(el.font_size * s / 72))
            fnt = (el.font_name, size_px, style) if style else (el.font_name, size_px)

            anchor_map = {"left": "nw", "center": "n", "right": "ne"}
            anchor = anchor_map.get(el.align, "nw")
            tx = x0 if el.align == "left" else (x0 + x1) / 2 if el.align == "center" else x1

            # Background box (light blue tint when selected)
            box_outline = SEL_COL if el.selected else ""
            box_fill    = "#e8e8ff" if el.selected else ""
            c.create_rectangle(x0, y0, x1, y1, fill=box_fill, outline=box_outline,
                                dash=(4,3) if el.selected else ())

            c.create_text(tx, y0, text=el.text, font=fnt, fill=el.color,
                          anchor=anchor, width=(x1 - x0))

        elif isinstance(el, ImageElement):
            x1, y1 = self._to_canvas(el.x + el.width, el.y + el.height)
            w_px = max(1, int((x1 - x0)))
            h_px = max(1, int((y1 - y0)))

            if PIL_AVAILABLE and el.path and os.path.isfile(el.path):
                try:
                    key = (el.id, w_px, h_px)
                    if key not in self._img_cache:
                        img = Image.open(el.path).convert("RGBA")
                        img = img.resize((w_px, h_px), Image.LANCZOS)
                        self._img_cache[key] = ImageTk.PhotoImage(img)
                    c.create_image(x0, y0, anchor="nw", image=self._img_cache[key])
                except Exception as e:
                    c.create_rectangle(x0, y0, x1, y1, fill="#ffeeee", outline="#cc0000")
                    c.create_text((x0+x1)/2, (y0+y1)/2, text="⚠ Image Error",
                                  fill="#cc0000", font=("Arial", 9))
            else:
                c.create_rectangle(x0, y0, x1, y1, fill="#eef0ff", outline="#8888aa",
                                   dash=(6,3))
                c.create_text((x0+x1)/2, (y0+y1)/2, text="🖼 Image\n(no file)",
                              fill="#888899", font=("Arial", 9), justify="center")

        # Selection handles
        if el.selected:
            x1, y1 = self._to_canvas(el.x + el.width, el.y + el.height)
            # Border
            c.create_rectangle(x0-1, y0-1, x1+1, y1+1,
                                outline=SEL_COL, width=2, dash=(5,3))
            # Corner handles
            hs = 6
            for hx, hy in [(x0,y0),(x1,y0),(x0,y1),(x1,y1),
                           ((x0+x1)/2,y0),((x0+x1)/2,y1),
                           (x0,(y0+y1)/2),(x1,(y0+y1)/2)]:
                c.create_rectangle(hx-hs, hy-hs, hx+hs, hy+hs,
                                   fill=HANDLE_COL, outline="white", width=1)

    # ══════════════════════════════════════════
    #  Mouse / Drag Interactions
    # ══════════════════════════════════════════

    def _on_canvas_press(self, event):
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        ix, iy = self._to_label(cx, cy)

        # Hit-test elements (back-to-front in reverse)
        hit = None
        for el in reversed(self.elements):
            w = getattr(el, "width",  2.0)
            h = getattr(el, "height", 0.4)
            if el.x <= ix <= el.x + w and el.y <= iy <= el.y + h:
                hit = el
                break

        # Deselect old
        if self.selected:
            self.selected.selected = False

        self.selected = hit
        if hit:
            hit.selected = True
            self._drag_data = {
                "el": hit,
                "start_ix": ix, "start_iy": iy,
                "orig_x": hit.x, "orig_y": hit.y,
            }
            self._update_properties()
        else:
            self._show_no_selection()

        self._refresh_canvas()

    def _on_canvas_drag(self, event):
        if not self._drag_data:
            return
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        ix, iy = self._to_label(cx, cy)

        el = self._drag_data["el"]
        dx = ix - self._drag_data["start_ix"]
        dy = iy - self._drag_data["start_iy"]
        el.x = max(0, self._drag_data["orig_x"] + dx)
        el.y = max(0, self._drag_data["orig_y"] + dy)
        self._refresh_canvas()
        # Update property spinboxes live
        self._update_properties()

    def _on_canvas_release(self, event):
        if self._drag_data:
            self._push_undo()
        self._drag_data = {}

    def _on_canvas_dblclick(self, event):
        if self.selected and isinstance(self.selected, TextElement):
            self._edit_text_popup(self.selected)

    def _on_canvas_rclick(self, event):
        menu = tk.Menu(self, tearoff=False, bg=PANEL_BG, fg=TEXT_COL,
                       activebackground=ACCENT, activeforeground="white")
        if self.selected:
            menu.add_command(label="Edit",   command=lambda: self._edit_text_popup(self.selected)
                             if isinstance(self.selected, TextElement) else None)
            menu.add_command(label="Copy",   command=self._copy)
            menu.add_command(label="Delete", command=self._delete)
            menu.add_separator()
            menu.add_command(label="Bring Forward", command=self._bring_forward)
            menu.add_command(label="Send Backward",  command=self._send_backward)
            menu.add_separator()
        menu.add_command(label="Add Text",  command=self._add_text)
        menu.add_command(label="Add Image", command=self._add_image)
        menu.add_command(label="Add Rect",  command=self._add_rect)
        menu.add_separator()
        menu.add_command(label="Paste", command=self._paste)
        menu.tk_popup(event.x_root, event.y_root)

    # ══════════════════════════════════════════
    #  Element Actions
    # ══════════════════════════════════════════

    def _add_text(self):
        el = TextElement(x=0.2, y=0.2, text="New Text")
        self.elements.append(el)
        self._select(el)
        self._push_undo()
        self._refresh_canvas()

    def _add_image(self):
        path = filedialog.askopenfilename(
            title="Choose Image",
            filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.gif *.tif *.webp"),
                       ("All","*.*")])
        if path:
            el = ImageElement(x=0.2, y=0.2, path=path, width=2.0, height=2.0)
            self.elements.append(el)
            self._select(el)
            self._push_undo()
            self._refresh_canvas()

    def _add_rect(self):
        el = RectElement(x=0.2, y=0.2, width=2.0, height=1.0)
        self.elements.append(el)
        self._select(el)
        self._push_undo()
        self._refresh_canvas()

    def _select(self, el):
        if self.selected:
            self.selected.selected = False
        self.selected = el
        if el:
            el.selected = True
        self._update_properties()

    def _update_properties(self):
        if self.selected is None:
            self._show_no_selection()
        elif isinstance(self.selected, TextElement):
            self._show_text_properties(self.selected)
        elif isinstance(self.selected, RectElement):
            self._show_rect_properties(self.selected)
        elif isinstance(self.selected, ImageElement):
            self._show_image_properties(self.selected)

    def _delete(self, event=None):
        if self.selected and self.selected in self.elements:
            self.elements.remove(self.selected)
            self.selected = None
            self._push_undo()
            self._show_no_selection()
            self._refresh_canvas()

    def _copy(self, event=None):
        if self.selected:
            self.clipboard = copy.deepcopy(self.selected)

    def _paste(self, event=None):
        if self.clipboard:
            el = copy.deepcopy(self.clipboard)
            el.id = LabelElement._id_counter + 1
            LabelElement._id_counter += 1
            el.x += 0.1
            el.y += 0.1
            self.elements.append(el)
            self._select(el)
            self._push_undo()
            self._refresh_canvas()

    def _select_all(self, event=None):
        pass  # multi-select not implemented; could be added

    def _bring_forward(self):
        if self.selected and self.selected in self.elements:
            i = self.elements.index(self.selected)
            if i < len(self.elements) - 1:
                self.elements[i], self.elements[i+1] = self.elements[i+1], self.elements[i]
                self._push_undo(); self._refresh_canvas()

    def _send_backward(self):
        if self.selected and self.selected in self.elements:
            i = self.elements.index(self.selected)
            if i > 0:
                self.elements[i], self.elements[i-1] = self.elements[i-1], self.elements[i]
                self._push_undo(); self._refresh_canvas()

    def _align(self, mode):
        if not self.selected:
            return
        el = self.selected
        w = getattr(el, "width",  0)
        h = getattr(el, "height", 0)
        if mode == "left":          el.x = 0
        elif mode == "right":       el.x = self.label_w - w
        elif mode == "center_h":    el.x = (self.label_w - w) / 2
        elif mode == "top":         el.y = 0
        elif mode == "bottom":      el.y = self.label_h - h
        elif mode == "center_v":    el.y = (self.label_h - h) / 2
        self._push_undo(); self._refresh_canvas()

    def _edit_text_popup(self, el: TextElement):
        win = tk.Toplevel(self)
        win.title("Edit Text")
        win.geometry("400x200")
        win.configure(bg=APP_BG)
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="Edit text content:", bg=APP_BG, fg=TEXT_COL).pack(pady=8)
        txt = tk.Text(win, height=5, font=("Arial", 13),
                      bg="#333350", fg=TEXT_COL, insertbackground="white")
        txt.pack(fill="both", expand=True, padx=16, pady=4)
        txt.insert("1.0", el.text)
        txt.focus_set()

        def apply():
            el.text = txt.get("1.0", "end-1c")
            self._refresh_canvas()
            win.destroy()

        tk.Button(win, text="OK", command=apply, bg=BTN_BG, fg="white",
                  relief="flat", padx=20).pack(pady=8)
        win.bind("<Return>", lambda e: apply())

    # ══════════════════════════════════════════
    #  Label Size / Preset
    # ══════════════════════════════════════════

    def _on_preset_change(self, event=None):
        preset = self._preset_var.get()
        size   = LABEL_PRESETS.get(preset)
        if size:
            self.label_w = size[0]
            self.label_h = size[1]
            self._w_var.set(round(size[0], 2))
            self._h_var.set(round(size[1], 2))
        self._refresh_canvas()

    def _on_size_change(self, *a):
        try:
            self.label_w = float(self._w_var.get())
            self.label_h = float(self._h_var.get())
            self._refresh_canvas()
        except: pass

    def _label_settings(self):
        win = tk.Toplevel(self)
        win.title("Label Settings")
        win.geometry("360x220")
        win.configure(bg=APP_BG)
        win.transient(self); win.grab_set()

        tk.Label(win, text="Label Width (inches):", bg=APP_BG, fg=TEXT_COL).pack(pady=6)
        wv = tk.DoubleVar(value=self.label_w)
        tk.Spinbox(win, textvariable=wv, from_=0.5, to=30, increment=0.1,
                   format="%.2f", width=10, bg="#333350", fg=TEXT_COL).pack()

        tk.Label(win, text="Label Height (inches):", bg=APP_BG, fg=TEXT_COL).pack(pady=6)
        hv = tk.DoubleVar(value=self.label_h)
        tk.Spinbox(win, textvariable=hv, from_=0.5, to=30, increment=0.1,
                   format="%.2f", width=10, bg="#333350", fg=TEXT_COL).pack()

        def apply():
            try:
                self.label_w = float(wv.get())
                self.label_h = float(hv.get())
                self._w_var.set(round(self.label_w, 2))
                self._h_var.set(round(self.label_h, 2))
                self._refresh_canvas()
                win.destroy()
            except: pass

        tk.Button(win, text="Apply", command=apply,
                  bg=BTN_BG, fg="white", relief="flat", padx=20).pack(pady=12)

    # ══════════════════════════════════════════
    #  Undo / Redo
    # ══════════════════════════════════════════

    def _push_undo(self):
        state = {
            "elements": [e.to_dict() for e in self.elements],
            "label_w":  self.label_w,
            "label_h":  self.label_h,
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore_state(self, state):
        self.label_w = state["label_w"]
        self.label_h = state["label_h"]
        self._w_var.set(round(self.label_w, 2))
        self._h_var.set(round(self.label_h, 2))
        self.elements = []
        for d in state["elements"]:
            kind = d["kind"]
            if kind == "text":
                self.elements.append(TextElement.from_dict(d))
            elif kind == "image":
                self.elements.append(ImageElement.from_dict(d))
            elif kind == "rect":
                self.elements.append(RectElement.from_dict(d))
        self.selected = None
        self._show_no_selection()
        self._refresh_canvas()

    def _undo(self, event=None):
        if len(self._undo_stack) > 1:
            self._redo_stack.append(self._undo_stack.pop())
            self._restore_state(self._undo_stack[-1])

    def _redo(self, event=None):
        if self._redo_stack:
            state = self._redo_stack.pop()
            self._undo_stack.append(state)
            self._restore_state(state)

    # ══════════════════════════════════════════
    #  File Operations
    # ══════════════════════════════════════════

    def _new_label(self, event=None):
        if messagebox.askyesno("New Label", "Create a new label? Unsaved changes will be lost."):
            self.elements.clear()
            self.selected = None
            self.label_w = 4.0; self.label_h = 6.0
            self._w_var.set(4.0); self._h_var.set(6.0)
            self._show_no_selection()
            self._push_undo()
            self._refresh_canvas()

    def _save_file(self, event=None):
        path = filedialog.asksaveasfilename(
            title="Save Label", defaultextension=".lbl",
            filetypes=[("Label files","*.lbl"),("JSON","*.json"),("All","*.*")])
        if path:
            data = {
                "version": "1.0",
                "label_w": self.label_w,
                "label_h": self.label_h,
                "elements": [e.to_dict() for e in self.elements],
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Label saved to:\n{path}")

    def _open_file(self, event=None):
        path = filedialog.askopenfilename(
            title="Open Label",
            filetypes=[("Label files","*.lbl"),("JSON","*.json"),("All","*.*")])
        if path:
            try:
                with open(path) as f:
                    data = json.load(f)
                self._restore_state(data)
                self._push_undo()
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")

    # ══════════════════════════════════════════
    #  Export / Print
    # ══════════════════════════════════════════

    def _render_to_pil(self, dpi=300) -> "Image.Image":
        """Render label to a PIL Image at given DPI."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is not installed.")

        w_px = int(self.label_w * dpi)
        h_px = int(self.label_h * dpi)
        img  = Image.new("RGB", (w_px, h_px), "white")
        draw = ImageDraw.Draw(img)

        for el in self.elements:
            ex  = int(el.x * dpi)
            ey  = int(el.y * dpi)
            ew  = int(getattr(el,"width", 1) * dpi)
            eh  = int(getattr(el,"height",1) * dpi)

            if isinstance(el, RectElement):
                fill   = el.fill   if el.fill   not in ("none","") else None
                stroke = el.stroke if el.stroke not in ("none","") else None
                sw     = max(1, int(el.stroke_width * dpi / 96))
                draw.rectangle([ex, ey, ex+ew, ey+eh],
                               fill=fill, outline=stroke, width=sw)

            elif isinstance(el, TextElement):
                fsize = max(6, int(el.font_size * dpi / 72))
                try:
                    style_suffix = ""
                    if el.bold and el.italic: style_suffix = " Bold Italic"
                    elif el.bold:  style_suffix = " Bold"
                    elif el.italic: style_suffix = " Italic"
                    fnt = ImageFont.truetype(el.font_name + style_suffix + ".ttf", fsize)
                except:
                    try:
                        fnt = ImageFont.truetype("arial.ttf", fsize)
                    except:
                        fnt = ImageFont.load_default()

                draw.text((ex, ey), el.text, fill=el.color, font=fnt)

            elif isinstance(el, ImageElement):
                if el.path and os.path.isfile(el.path):
                    try:
                        src = Image.open(el.path).convert("RGBA")
                        src = src.resize((ew, eh), Image.LANCZOS)
                        img.paste(src, (ex, ey), src)
                    except: pass

        return img

    def _export_png(self, event=None):
        if not PIL_AVAILABLE:
            messagebox.showerror("Error", "Pillow is required for PNG export.\npip install pillow")
            return
        path = filedialog.asksaveasfilename(
            title="Export PNG", defaultextension=".png",
            filetypes=[("PNG","*.png"),("All","*.*")])
        if path:
            try:
                img = self._render_to_pil(dpi=300)
                img.save(path, dpi=(300,300))
                messagebox.showinfo("Exported", f"PNG exported to:\n{path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _export_pdf(self, event=None):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error",
                "ReportLab is required for PDF export.\npip install reportlab")
            return
        path = filedialog.asksaveasfilename(
            title="Export PDF", defaultextension=".pdf",
            filetypes=[("PDF","*.pdf"),("All","*.*")])
        if not path:
            return
        try:
            w_pt = self.label_w * inch
            h_pt = self.label_h * inch
            c = rl_canvas.Canvas(path, pagesize=(w_pt, h_pt))
            c.setPageSize((w_pt, h_pt))

            # ReportLab origin is bottom-left; convert y
            def rl_y(iy, ih=0):
                return h_pt - (iy + ih) * inch

            for el in self.elements:
                if isinstance(el, RectElement):
                    # Fill
                    if el.fill and el.fill != "none":
                        r,g,b = self._hex_to_rgb(el.fill)
                        c.setFillColorRGB(r,g,b)
                        c.rect(el.x*inch, rl_y(el.y, el.height),
                               el.width*inch, el.height*inch, stroke=0, fill=1)
                    # Stroke
                    if el.stroke and el.stroke != "none" and el.stroke_width > 0:
                        r,g,b = self._hex_to_rgb(el.stroke)
                        c.setStrokeColorRGB(r,g,b)
                        c.setLineWidth(el.stroke_width)
                        c.rect(el.x*inch, rl_y(el.y, el.height),
                               el.width*inch, el.height*inch, stroke=1, fill=0)

                elif isinstance(el, TextElement):
                    r,g,b = self._hex_to_rgb(el.color)
                    c.setFillColorRGB(r,g,b)
                    style = ""
                    if el.bold and el.italic: style = "BoldItalic"
                    elif el.bold:   style = "Bold"
                    elif el.italic: style = "Oblique"

                    try:
                        font_map = {
                            "Arial":   "Helvetica",
                            "Times New Roman": "Times-Roman",
                            "Courier New": "Courier",
                        }
                        rl_font = font_map.get(el.font_name, "Helvetica")
                        if style and rl_font == "Helvetica":
                            rl_font = f"Helvetica-{style}"
                        c.setFont(rl_font, el.font_size)
                    except:
                        c.setFont("Helvetica", el.font_size)

                    ty = rl_y(el.y) - el.font_size * 0.8
                    if el.align == "center":
                        c.drawCentredString((el.x + el.width/2)*inch, ty, el.text)
                    elif el.align == "right":
                        c.drawRightString((el.x + el.width)*inch, ty, el.text)
                    else:
                        c.drawString(el.x*inch, ty, el.text)

                elif isinstance(el, ImageElement):
                    if el.path and os.path.isfile(el.path):
                        try:
                            c.drawImage(el.path, el.x*inch, rl_y(el.y, el.height),
                                        el.width*inch, el.height*inch,
                                        preserveAspectRatio=False, mask="auto")
                        except: pass

            c.save()
            messagebox.showinfo("PDF Exported",
                f"PDF saved:\n{path}\n\nSize: {self.label_w}\" × {self.label_h}\"")
        except Exception as e:
            messagebox.showerror("PDF Export Error", str(e))
            
            
    def _print_label(self, event=None):

        try:
            tspl = []

            # ==================================================
            # Label Sheet Configuration
            # ==================================================
            LABEL_WIDTH_MM = 38
            LABEL_HEIGHT_MM = 25

            COLUMNS = 2
            ROWS = 1

            HORIZONTAL_GAP_MM = 0
            VERTICAL_GAP_MM = 3

            DPI = 203
            DOTS_PER_MM = DPI / 25.4

            LABEL_WIDTH_DOTS = int(LABEL_WIDTH_MM * DOTS_PER_MM)
            LABEL_HEIGHT_DOTS = int(LABEL_HEIGHT_MM * DOTS_PER_MM)

            HORIZONTAL_GAP_DOTS = int(HORIZONTAL_GAP_MM * DOTS_PER_MM)
            VERTICAL_GAP_DOTS = int(VERTICAL_GAP_MM * DOTS_PER_MM)

            TOTAL_WIDTH_MM = (
                COLUMNS * LABEL_WIDTH_MM +
                (COLUMNS - 1) * HORIZONTAL_GAP_MM
            )

            TOTAL_HEIGHT_MM = (
                ROWS * LABEL_HEIGHT_MM +
                (ROWS - 1) * VERTICAL_GAP_MM
            )

            # ==================================================
            # TSPL Header
            # ==================================================
            tspl.append(f"SIZE {TOTAL_WIDTH_MM} mm,{TOTAL_HEIGHT_MM} mm")
            tspl.append("GAP 2 mm,0")
            tspl.append("DIRECTION 1")
            tspl.append("CLS")

            # ==================================================
            # Draw Elements
            # ==================================================
            for el in self.elements:

                if isinstance(el, TextElement):

                    text = el.text.replace('"', "'")

                    x = int(el.x)
                    y = int(el.y)

                    for row in range(ROWS):

                        for col in range(COLUMNS):

                            offset_x = col * (
                                LABEL_WIDTH_DOTS +
                                HORIZONTAL_GAP_DOTS
                            )

                            offset_y = row * (
                                LABEL_HEIGHT_DOTS +
                                VERTICAL_GAP_DOTS
                            )

                            tspl.append(
                                f'TEXT {x + offset_x},{y + offset_y},"1",0,2,2,"{text}"'
                            )

            # ==================================================
            # Print
            # ==================================================
            tspl.append("PRINT 1")

            tspl_data = ("\r\n".join(tspl) + "\r\n").encode("ascii")

            printer_name = win32print.GetDefaultPrinter()

            hPrinter = win32print.OpenPrinter(printer_name)

            try:
                win32print.StartDocPrinter(
                    hPrinter,
                    1,
                    ("Label Print", None, "RAW")
                )

                win32print.StartPagePrinter(hPrinter)
                win32print.WritePrinter(hPrinter, tspl_data)
                win32print.EndPagePrinter(hPrinter)
                win32print.EndDocPrinter(hPrinter)

            finally:
                win32print.ClosePrinter(hPrinter)

            # ==================================================
            # Debug
            # ==================================================
            print("=" * 60)
            print("\n".join(tspl))
            print("=" * 60)

            messagebox.showinfo(
                "Success",
                f"Printed {ROWS * COLUMNS} identical labels successfully.\n\n"
                f"Printer : {printer_name}\n"
                f"Layout : {COLUMNS} × {ROWS}\n"
                f"Label Size : {LABEL_WIDTH_MM} × {LABEL_HEIGHT_MM} mm"
            )

        except Exception as e:
            messagebox.showerror(
                "Print Error",
                str(e)
            )
    
    # ══════════════════════════════════════════
    #  Keyboard shortcuts
    # ══════════════════════════════════════════

    def _bind_shortcuts(self):
        self.bind("<Control-z>", self._undo)
        self.bind("<Control-y>", self._redo)
        self.bind("<Control-c>", self._copy)
        self.bind("<Control-v>", self._paste)
        self.bind("<Delete>",    self._delete)
        self.bind("<BackSpace>", self._delete)
        self.bind("<Control-s>", self._save_file)
        self.bind("<Control-o>", self._open_file)
        self.bind("<Control-n>", self._new_label)
        self.bind("<Control-p>", self._print_label)
        self.bind("<Control-e>", self._export_pdf)

        # Arrow key nudge
        step = 0.01  # inches
        for key, dx, dy in [("<Left>", -step, 0), ("<Right>", step, 0),
                             ("<Up>",   0, -step), ("<Down>",  0,  step)]:
            self.bind(key, lambda e, dx=dx, dy=dy: self._nudge(dx, dy))
        # Shift+arrow = bigger nudge
        for key, dx, dy in [("<Shift-Left>", -0.1, 0), ("<Shift-Right>", 0.1, 0),
                             ("<Shift-Up>",   0, -0.1), ("<Shift-Down>",  0,  0.1)]:
            self.bind(key, lambda e, dx=dx, dy=dy: self._nudge(dx, dy))

    def _nudge(self, dx, dy):
        if self.selected:
            self.selected.x = max(0, self.selected.x + dx)
            self.selected.y = max(0, self.selected.y + dy)
            self._refresh_canvas()

    # ══════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════

    def _hex_to_rgb(self, hex_color: str):
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        return r, g, b


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = LabelPrinterApp()
    app.mainloop()
