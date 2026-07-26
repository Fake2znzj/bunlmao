@echo off
echo ⬡ Starting Antares (Python wrapper)...
python main.py
if errorlevel 1 (
  echo Trying python3...
  python3 main.py
)
pause
