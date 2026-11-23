# SmartSite Enterprise Platform Launcher
$Host.UI.RawUI.WindowTitle = "SmartSite AI Construction Safety Platform"
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host " SmartSite Enterprise AI Construction Safety Platform" -ForegroundColor Yellow
Write-Host " FastAPI + InsightFace ArcFace + Ultralytics YOLO11n + WebSocket Event Bus" -ForegroundColor Green
Write-Host "=========================================================================" -ForegroundColor Cyan
$env:OPENBLAS_NUM_THREADS = "2"
$env:OMP_NUM_THREADS = "2"
$env:MKL_NUM_THREADS = "2"
python main.py
