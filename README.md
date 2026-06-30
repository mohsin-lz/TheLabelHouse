# Label Printer Pro 🖨️
### Professional Label Design & Printing Tool

---

## 📦 What's Included

| File | Purpose |
|------|---------|
| `label_printer.py` | Main application source code |
| `requirements.txt` | Python package dependencies |
| `BUILD_TO_EXE.bat` | One-click build to .exe (Windows) |

---

## 🚀 Quick Start (Run from Python)

1. **Install Python 3.8+** from https://python.org

2. **Install dependencies:**
   ```
   pip install pillow reportlab
   ```

3. **Run the app:**
   ```
   python label_printer.py
   ```

---

## 🏗️ Build to .exe (Windows)

1. Double-click `BUILD_TO_EXE.bat`
2. Wait ~60 seconds for build to complete
3. Find your exe at: `dist\LabelPrinterPro.exe`
4. Copy it anywhere — fully standalone!

**Manual build command:**
```
pip install pyinstaller
pyinstaller --onefile --windowed --name "LabelPrinterPro" label_printer.py
```

---

## 🎨 Features

### Label Sizes
- **4×6 inch** — Amazon/Flipkart shipping labels (default)
- **4×4 inch** — Square product labels
- **3×2 inch** — Small product labels  
- **2×1 inch** — Barcode/price tags
- **3.5×1 inch** — File/box labels
- **A4 Full Page**
- **Custom** — Enter any size in inches

### Elements
- **Text** — Drag, resize, edit font/size/color/alignment/bold/italic
- **Images** — PNG, JPG, BMP, GIF, TIFF, WEBP
- **Rectangles** — Custom fill, stroke, width

### Editing
- Drag elements to reposition
- Resize via Properties panel
- Double-click text to edit inline
- Right-click for context menu
- Undo/Redo (Ctrl+Z / Ctrl+Y)
- Copy/Paste (Ctrl+C / Ctrl+V)
- Delete (Delete key)
- Arrow keys to nudge (Shift+Arrow = bigger nudge)
- Alignment tools: left/center/right/top/middle/bottom
- Layer order: Bring Forward / Send Backward

### Save & Export
- **Save/Open** project files (.lbl / .json)
- **Export PDF** — exact label size, print-ready
- **Export PNG** — 300 DPI high resolution
- **Print** — sends to system print dialog with correct label dimensions

---

## 🖨️ Printing Tips

When the print dialog opens:
1. Select your **thermal/label printer**
2. Set paper size to **4×6 inch** (or your label size)
3. Set all **margins to 0**
4. **Disable** "Fit to page" or "Scale to fit"
5. Print!

For thermal printers (Zebra, TSC, XPRINTER etc.):
- Create a custom paper size matching your label roll
- Width: 4 inch (101.6 mm), Height: 6 inch (152.4 mm)

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New label |
| Ctrl+O | Open project |
| Ctrl+S | Save project |
| Ctrl+P | Print |
| Ctrl+E | Export PDF |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+C | Copy element |
| Ctrl+V | Paste element |
| Delete | Delete element |
| Arrow Keys | Nudge (0.01") |
| Shift+Arrows | Nudge (0.1") |

---

## 🔧 Requirements

- Python 3.8 or higher
- `pillow` — image support, PNG export
- `reportlab` — PDF generation and printing
- `tkinter` — GUI (included with Python on Windows/Mac)

> **Note:** On some Linux systems, install tkinter with:
> `sudo apt install python3-tk`
