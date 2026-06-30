import tkinter as tk
from tkinter import ttk
from tkinter import font
from PIL import Image, ImageDraw, ImageFont, ImageWin
import win32print
import win32ui
from win32con import HORZRES, VERTRES, PHYSICALWIDTH, PHYSICALHEIGHT

# --------------------------------------------------
# Choose Label Size
# --------------------------------------------------
# Option 1
LABEL_WIDTH_MM = 38
LABEL_HEIGHT_MM = 25

# Option 2
# LABEL_WIDTH_MM = 82.55     # 3.25 inch
# LABEL_HEIGHT_MM = 25.4     # 1.00 inch

MM_TO_PIXEL = 8      # only for screen display

CANVAS_W = int(LABEL_WIDTH_MM * MM_TO_PIXEL)
CANVAS_H = int(LABEL_HEIGHT_MM * MM_TO_PIXEL)

# Printing resolution
PRINT_DPI = 300
MM_TO_INCH = 1 / 25.4

PRINT_W = int(LABEL_WIDTH_MM * MM_TO_INCH * PRINT_DPI)
PRINT_H = int(LABEL_HEIGHT_MM * MM_TO_INCH * PRINT_DPI)


class LabelDesigner:

    def __init__(self, root):

        self.root = root
        self.root.title("Label Designer")

        top = tk.Frame(root)
        top.pack(fill="x", padx=5, pady=5)

        tk.Label(top, text="Text").pack(side="left")

        self.text_var = tk.StringVar(value="Sample Text")

        entry = tk.Entry(top, textvariable=self.text_var, width=25)
        entry.pack(side="left", padx=5)
        entry.bind("<KeyRelease>", self.update_text)

        tk.Label(top, text="Font Size").pack(side="left")

        self.size_var = tk.IntVar(value=24)

        spin = tk.Spinbox(
            top,
            from_=6,
            to=120,
            width=5,
            textvariable=self.size_var,
            command=self.update_font,
        )
        spin.pack(side="left")
        spin.bind("<KeyRelease>", lambda e: self.update_font())

        tk.Button(top, text="Print", command=self.print_label).pack(
            side="right", padx=10
        )

        self.canvas = tk.Canvas(
            root,
            width=CANVAS_W,
            height=CANVAS_H,
            bg="white",
            highlightbackground="black",
        )
        self.canvas.pack(padx=10, pady=10)

        self.font = ("Arial", self.size_var.get())

        self.text_item = self.canvas.create_text(
            CANVAS_W // 2,
            CANVAS_H // 2,
            text=self.text_var.get(),
            font=self.font,
            anchor="center",
            fill="black",
        )

        self.canvas.tag_bind(self.text_item, "<Button-1>", self.start_move)
        self.canvas.tag_bind(self.text_item, "<B1-Motion>", self.move_text)

    def update_text(self, event=None):
        self.canvas.itemconfig(self.text_item, text=self.text_var.get())

    def update_font(self, event=None):
        self.canvas.itemconfig(
            self.text_item,
            font=("Arial", int(self.size_var.get()))
        )

    def start_move(self, event):
        self.lastx = event.x
        self.lasty = event.y

    def move_text(self, event):
        dx = event.x - self.lastx
        dy = event.y - self.lasty

        self.canvas.move(self.text_item, dx, dy)

        self.lastx = event.x
        self.lasty = event.y

    def print_label(self):

        printer = win32print.GetDefaultPrinter()

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer)
    
        # Landscape
        devmode = hdc.GetDeviceCaps
        hdc.StartDoc("Labels")
        hdc.StartPage()
    
        # Printer DPI
        dpi = 300
    
        mm_to_px = lambda mm: int(mm / 25.4 * dpi)
    
        label_w = mm_to_px(38)
        label_h = mm_to_px(25)
    
        gap = mm_to_px(3)       # if you want horizontal gap change here
    
        page = Image.new(
            "RGB",
            (label_w * 2 + gap, label_h),
            "white"
        )
    
        # Create one label
        label = Image.new("RGB", (label_w, label_h), "white")
        draw = ImageDraw.Draw(label)
    
        x_screen, y_screen = self.canvas.coords(self.text_item)
    
        x = int(x_screen / CANVAS_W * label_w)
        y = int(y_screen / CANVAS_H * label_h)
    
        fontsize = int(self.size_var.get() * dpi / 96)
    
        try:
            font = ImageFont.truetype("arial.ttf", fontsize)
        except:
            font = ImageFont.load_default()
    
        text = self.text_var.get()
    
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    
        draw.text(
            (x - tw/2, y - th/2),
            text,
            fill="black",
            font=font
        )
    
        # Paste label twice
        page.paste(label, (0, 0))
        page.paste(label, (label_w + gap, 0))
    
        dib = ImageWin.Dib(page)
    
        dib.draw(
            hdc.GetHandleOutput(),
            (
                0,
                0,
                label_w * 2 + gap,
                label_h
            )
        )
    
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()


root = tk.Tk()
LabelDesigner(root)
root.mainloop()