"""
SmartSite — Commercial AI Construction Safety Platform.
Production FastAPI Server with WebSocket Event Bus and Low-Latency Video Streaming.
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
from database.db import init_db
from api import api_router
from core.ws_manager import ws_manager
from core.camera_streamer import camera_service
from safety.event_engine import get_event_engine
from database.models import SafetyEvent

# Register real-time event engine listener to push alerts over WebSocket
def on_safety_event(event: SafetyEvent):
    # Schedule async broadcast in the running asyncio loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast_json("incident_alert", event.to_dict()),
                loop
            )
    except Exception:
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database and background CV services
    init_db()
    event_engine = get_event_engine()
    event_engine.register_listener(on_safety_event)
    
    # Start live camera background processing worker
    camera_service.start()
    yield
    # Shutdown: Release OpenCV cameras & worker threads
    camera_service.stop()

app = FastAPI(
    title="SmartSite — AI Construction Safety Platform",
    description="Enterprise Computer Vision & IoT Safety Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount evidence, faces & dataset directories so the browser can load photos
app.mount("/evidence", StaticFiles(directory=config.EVIDENCE_DIR), name="evidence")
app.mount("/faces", StaticFiles(directory=config.FACES_DIR), name="faces")
dataset_img_dir = os.path.join(config.DATA_DIR, "datasets", "construction-ppe", "images", "train")
if os.path.exists(dataset_img_dir):
    app.mount("/dataset_images", StaticFiles(directory=dataset_img_dir), name="dataset_images")
app.mount("/static", StaticFiles(directory=os.path.join(config.BASE_DIR, "static")), name="static")

# WebSocket Endpoint for live alerts & telemetry
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive ping/pong
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Root Endpoint: Serves Commercial Web Dashboard
@app.get("/")
def serve_dashboard():
    index_path = os.path.join(config.BASE_DIR, "static", "index.html")
    return FileResponse(index_path)

if __name__ == "__main__":
    import uvicorn
    print("=" * 65)
    print(" SmartSite Enterprise AI Construction Safety Platform")
    print(f" Server URL: http://{config.HOST}:{config.PORT}")
    print(f" API Docs:   http://{config.HOST}:{config.PORT}/docs")
    print("=" * 65)
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
