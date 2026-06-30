@echo off
echo ========================================================
echo  Label Printer Pro - Build Script
echo ========================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
pip install pillow reportlab pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Building executable...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "LabelPrinterPro" ^
    --icon=icon.ico ^
    --add-data "." ^
    --hidden-import PIL ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import reportlab ^
    --hidden-import reportlab.pdfgen ^
    --hidden-import reportlab.lib ^
    label_printer.py

if %errorlevel% neq 0 (
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

echo [3/3] Done!
echo.
echo Your executable is at:
echo   dist\LabelPrinterPro.exe
echo.
echo You can copy LabelPrinterPro.exe anywhere - it is standalone!
pause
