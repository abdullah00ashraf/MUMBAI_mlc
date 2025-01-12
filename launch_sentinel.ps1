# ====================================================================
# PROJECT SALSETTE // SENTINEL V7 - POWERSHELL DEPLOYMENT MATRIX
# ====================================================================

$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   INITIATING PROJECT SALSETTE // SENTINEL V7 ENGINES    " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

# Array to store our background process IDs
$script:activePids = @()

try {
    # A. Start the Background Telemetry Daemon
    Write-Host ">>> [1/3] Booting Live Telemetry Ingestion Daemon..." -ForegroundColor Yellow
    $proc1 = Start-Process -FilePath "python" -ArgumentList "08_live_telemetry_daemon.py" -WorkingDirectory ".\HUFP_mumbai" -PassThru -NoNewWindow
    $script:activePids += $proc1.Id

    # B. Start the FastAPI Backend (Uvicorn)
    Write-Host ">>> [2/3] Booting FastAPI Backend Engine (Port 8000)..." -ForegroundColor Yellow
    $proc2 = Start-Process -FilePath "uvicorn" -ArgumentList "api.main:app --host 127.0.0.1 --port 8000 --reload" -WorkingDirectory ".\HUFP_mumbai" -PassThru -NoNewWindow
    $script:activePids += $proc2.Id

    # C. Start the Frontend HTTP Server (Running from workspace root)
    Write-Host ">>> [3/3] Booting Tactical UI Server (Port 8080)..." -ForegroundColor Yellow
    $proc3 = Start-Process -FilePath "python" -ArgumentList "-m http.server 8080" -WorkingDirectory "." -PassThru -NoNewWindow
    $script:activePids += $proc3.Id

    Write-Host "=========================================================" -ForegroundColor Green
    Write-Host "   ALL SYSTEMS ONLINE AND SECURED.                       " -ForegroundColor Green
    Write-Host "                                                         "
    Write-Host "   -> Admin Node:   http://127.0.0.1:8080/HUFP_mumbai/web/admin/index.html"
    Write-Host "   -> Citizen Node: http://127.0.0.1:8080/HUFP_mumbai/web/citizen/index.html"
    Write-Host "                                                         "
    Write-Host "   [PRESS CTRL+C TO TERMINATE ALL SERVICES]              " -ForegroundColor Red
    Write-Host "=========================================================" -ForegroundColor Green

    # Keep the script alive to listen for Ctrl+C
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    # This block executes immediately when you press Ctrl+C
    Write-Host "`n=========================================================" -ForegroundColor Cyan
    Write-Host "   INITIATING SHUTDOWN PROTOCOL...                       " -ForegroundColor Cyan
    Write-Host "=========================================================" -ForegroundColor Cyan
    Write-Host "Terminating FastAPI Backend, Telemetry Daemon, and UI..." -ForegroundColor Yellow

    # Force kill the stored process IDs
    foreach ($pidToKill in $script:activePids) {
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "Ports 8000 and 8080 successfully cleared. System offline." -ForegroundColor Green
}