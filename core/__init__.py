"""
SmartSite Core Services Package.
High-performance camera streaming, WebSocket communication, and service orchestration.
"""
from core.ws_manager import ws_manager
from core.camera_streamer import camera_service

__all__ = ["ws_manager", "camera_service"]
