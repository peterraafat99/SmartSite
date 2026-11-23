# SmartSite — Enterprise AI Construction Safety Platform

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![YOLO11n](https://img.shields.io/badge/Ultralytics-YOLO11n-green.svg)](https://github.com/ultralytics/ultralytics)
[![InsightFace ArcFace](https://img.shields.io/badge/Biometrics-InsightFace%20ArcFace-cyan.svg)](https://github.com/deepinsight/insightface)
[![OSHA Aligned](https://img.shields.io/badge/OSHA-29%20CFR%201926-orange.svg)](https://www.osha.gov/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SmartSite** is an enterprise-grade AI-powered construction site safety monitoring platform.  
It combines real-time computer vision for PPE compliance, biometric face-recognition access control, software-defined virtual danger zones, and simulated IoT atmospheric sensors — all inside a dark industrial operations dashboard.

> ⚠️ **Disclaimer:** SmartSite is a functional software engineering prototype. IoT sensor values are simulated. AI detections are OSHA-aligned workflow aids and do not constitute certified legal compliance determinations.

---

## ✨ Features

| Module | Description |
|---|---|
| 🎯 **AI Vision & PPE Inspection** | Upload any construction site photo. YOLO11n detects workers, hardhat/vest compliance, and violations in real time. |
| 🚧 **Virtual Danger Zone (ROI)** | Custom software-defined restricted perimeter (NOT from dataset). Supervisors draw a rectangle; the system flags any worker whose feet touch it. OSHA Subpart P inspired. |
| 🪪 **Biometric Face Gate** | InsightFace ArcFace 512-d embedding-based facial recognition turnstile. Enroll workers with a photo, verify identity at the gate. |
| 🌡️ **IoT Environmental Sensors** | Simulated atmospheric gateway: temperature, humidity, PM2.5 dust, CO/VOC gas, acoustic noise. Scenario presets: Heat Stress, Gas Leak, etc. |
| 📊 **Operations Command Center** | Live KPI dashboard: PPE compliance rate, active incidents, critical alarms, AI Risk Gauge. |
| 📋 **Safety Incidents & Audit Log** | Full incident lifecycle (Open → Acknowledged → Resolved). CSV export for OSHA audit. |
| 📖 **OSHA Standards Library** | Built-in 29 CFR 1926 regulation reference cards. |

---

## 🏗️ Architecture

```
SmartSite/
├── main.py                  # FastAPI server entry point
├── config.py                # Paths, ports, model config
├── requirements.txt
│
├── ai/
│   ├── video_processor.py   # YOLO inference + PPE rule engine
│   └── zone_detector.py     # Virtual danger zone geometry logic
│
├── api/
│   ├── workers.py           # Worker enrollment & face gate API
│   ├── streaming.py         # Single-image analysis endpoint
│   ├── incidents.py         # Incident CRUD + CSV export
│   └── dashboard.py         # KPI stats & chart data
│
├── core/
│   ├── camera_streamer.py   # Background CV worker
│   └── ws_manager.py        # WebSocket real-time event bus
│
├── database/
│   ├── db.py                # SQLite init
│   └── models.py            # SQLAlchemy ORM models
│
├── iot/
│   └── simulator.py         # Simulated atmospheric sensor gateway
│
├── safety/
│   └── event_engine.py      # OSHA-aligned rule engine & alert dispatcher
│
├── static/
│   ├── index.html           # Single-page app (Vanilla JS + TailwindCSS)
│   ├── css/style.css        # Dark industrial glassmorphic theme
│   └── js/app.js            # Dashboard SPA engine (~1650 lines)
│
└── data/
    ├── datasets/            # Construction-PPE dataset (not tracked in git)
    ├── faces/               # Enrolled worker face photos (not tracked)
    └── evidence/            # Incident snapshot photos (not tracked)
```

---

## 🚀 Quick Start

### 1. Prerequisites

```bash
Python 3.10+
pip install -r requirements.txt
```

Required: `fastapi`, `uvicorn`, `ultralytics`, `insightface`, `onnxruntime`, `opencv-python`, `sqlalchemy`

### 2. Download Model Weights

```bash
# YOLO11n (auto-downloads on first run via ultralytics)
# OR manually place yolo11n.pt in project root
```

InsightFace buffalo_l model downloads automatically on first run.

### 3. Download Dataset (Optional — for AI Vision tab)

Download [Construction-PPE Dataset from Roboflow](https://universe.roboflow.com/construction-site-safety/construction-ppeobject-detection) in YOLOv8 format and extract to:
```
data/datasets/construction-ppe/
├── images/train/
├── images/val/
├── labels/train/
└── data.yaml
```

### 4. Run

```bash
python main.py
# → http://127.0.0.1:8000
```

---

## 📸 Dataset & Model Notes

| Component | Detail |
|---|---|
| **Dataset** | Construction-PPE (Roboflow) — 12 classes: `helmet`, `no_helmet`, `vest`, `no_vest`, `Person`, `forklift`, `gloves`, `boots`, `goggles`, `no_goggle`, `no_gloves`, `no_boots` |
| **Detection Model** | YOLO11n (Ultralytics) — COCO pretrained, fine-tunable on Construction-PPE |
| **Virtual Danger Zone** | Custom software-only ROI geometry check — **not a trained model, not from dataset** |
| **Face Recognition** | InsightFace ArcFace 512-d embeddings via buffalo_l (RetinaFace detector) |

> **To improve PPE detection accuracy:** Train YOLO on the full dataset for 100+ epochs:
> ```bash
> yolo train model=yolo11n.pt data=data/datasets/construction-ppe/data.yaml epochs=100 imgsz=640
> ```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serve dashboard SPA |
| `/api/v1/stream/analyze_image` | POST | Run YOLO + zone analysis on uploaded or dataset image |
| `/api/v1/workers` | GET | List enrolled workers |
| `/api/v1/workers/enroll` | POST | Enroll new worker with ArcFace biometric |
| `/api/v1/workers/verify` | POST | Verify face against enrolled workers |
| `/api/v1/incidents` | GET/POST | Safety incident CRUD |
| `/api/v1/incidents/export/csv` | GET | Export audit CSV |
| `/api/v1/dashboard/stats` | GET | Live KPI stats |
| `/api/v1/iot/current` | GET | Current IoT sensor readings |
| `/api/v1/iot/preset` | POST | Apply IoT simulation scenario |
| `/ws` | WebSocket | Real-time incident alerts |
| `/docs` | GET | Interactive Swagger API docs |

---

## 📝 License

MIT License — see [LICENSE](LICENSE)

---

*Built with FastAPI · YOLO11n · InsightFace ArcFace · SQLite · Vanilla JS · TailwindCSS*
