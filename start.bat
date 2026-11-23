@echo off
title SmartSite Enterprise AI Construction Safety Platform
echo =========================================================================
echo  Starting SmartSite Enterprise AI Construction Safety Platform
echo  FastAPI + InsightFace ArcFace + Ultralytics YOLO11n + WebSocket Event Bus
echo =========================================================================
set OPENBLAS_NUM_THREADS=2
set OMP_NUM_THREADS=2
set MKL_NUM_THREADS=2
python main.py
pause
