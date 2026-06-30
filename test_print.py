import win32print

PRINTER_NAME = "TSC TE244"   # Change this if your printer has a different name

tspl = """
SIZE 38 mm,25 mm
GAP 2 mm,0
CLS
TEXT 30,30,"3",0,2,2,"HELLO"
PRINT 1
"""

hPrinter = win32print.OpenPrinter(PRINTER_NAME)

try:
    hJob = win32print.StartDocPrinter(
        hPrinter,
        1,
        ("TSPL Test", None, "RAW")
    )

    win32print.StartPagePrinter(hPrinter)
    win32print.WritePrinter(hPrinter, tspl.encode("ascii"))
    win32print.EndPagePrinter(hPrinter)
    win32print.EndDocPrinter(hPrinter)

    print("Sent!")

finally:
    win32print.ClosePrinter(hPrinter)