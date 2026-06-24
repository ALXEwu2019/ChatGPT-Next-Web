@echo off
setlocal
cd /d "%~dp0"

if not exist "config.json" (
  echo %date% %time% ERROR config.json not found in %cd%>> logs\sync_batch_summary.log
  exit /b 1
)

if not exist "logs" mkdir logs

echo ===== %date% %time% sync start =====>> logs\sync_batch_summary.log
python sync_batch_summary.py -v>> logs\sync_batch_summary.log 2>&1
echo ===== %date% %time% sync done =====>> logs\sync_batch_summary.log

endlocal
