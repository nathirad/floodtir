@echo off
setlocal

set ROOT=D:\Floodtir\Floodtir
set PYTHON=C:\msys64\ucrt64\bin\python3.exe
set LOG=%ROOT%\update.log

>> "%LOG%" echo.
>> "%LOG%" echo ===== %date% %time% =====

cd /d "%ROOT%\scripts"

>> "%LOG%" echo [1/2] Fetching latest water levels from BMA...
"%PYTHON%" run_scraper.py latest --format full --output "%ROOT%\water-data\water_latest_snapshot.json" >> "%LOG%" 2>&1

if errorlevel 1 (
    >> "%LOG%" echo ERROR: Scraper failed, skipping rebuild.
    exit /b 1
)

>> "%LOG%" echo [2/2] Rebuilding flood_bkk_map.html...
"%PYTHON%" build_map.py >> "%LOG%" 2>&1

if errorlevel 1 (
    >> "%LOG%" echo ERROR: build_map.py failed.
    exit /b 1
)

>> "%LOG%" echo Done.
exit /b 0
