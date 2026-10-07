@echo off
echo ==============================================
echo Building siAgent Standalone Executable
echo ==============================================

echo [1/3] Installing PyInstaller...
pip install pyinstaller

echo [2/3] Building the executable...
C:\Users\rober\AppData\Roaming\Python\Python314\Scripts\pyinstaller.exe --noconfirm --clean --onefile --name siAgent ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import "pynvml" ^
    --hidden-import "psutil" ^
    --hidden-import "flask" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL._tkinter_finder" ^
    monitor.py

echo [3/3] Build complete!
echo.
echo Your standalone executable is located in the "dist" folder:
echo dist\siAgent.exe
echo.
echo You can copy this .exe file to any Windows computer and run it directly.
pause
