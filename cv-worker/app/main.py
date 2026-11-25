"""CV Worker runtime loop, health/metrics server (:9101), and back-pressure frame dropper."""

from __future__ import annotations

import contextlib
import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import cv2
import structlog
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from valkey import Valkey

from app.config import get_cv_settings
from app.worker import CameraPipelineConfig, CameraProcessor, KillSwitchClient

FRAMES_PROCESSED = Counter(
    "tp_cv_frames_processed_total", "Total frames processed per camera", ["camera_id"]
)
INFERENCE_LATENCY = Histogram(
    "tp_cv_inference_duration_ms", "CV inference duration per frame in ms"
)
CAMERA_STATUS = Gauge(
    "tp_cv_camera_status", "Camera online status (1=online, 0=offline)", ["camera_id"]
)

_stop_event = threading.Event()
logger = structlog.get_logger("cv_main")


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/metrics":
            data = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def _start_metrics_server(port: int = 9101) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), _MetricsHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _run_camera_loop(proc: CameraProcessor) -> None:
    """Process frames from RTSP/Demo MP4 with exponential reconnect and frame dropping."""
    backoff = 1.0
    cap: Any = None
    settings = get_cv_settings()

    while not _stop_event.is_set():
        src = proc.cfg.stream_url
        if proc.cfg.stream_type == "DEMO_MP4" and not Path(src).exists():
            src = settings.demo_video_path
        if not Path(src).exists() and proc.cfg.stream_type == "DEMO_MP4":
            time.sleep(2.0)
            continue

        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            CAMERA_STATUS.labels(proc.cfg.camera_id).set(0)
            proc.process_frame(None, timestamp_s=time.time(), camera_online=False)
            time.sleep(backoff)
            backoff = min(60.0, backoff * 2.0)
            continue

        backoff = 1.0
        CAMERA_STATUS.labels(proc.cfg.camera_id).set(1)
        last_infer_s = 0.0
        while not _stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                if proc.cfg.stream_type == "DEMO_MP4":
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                CAMERA_STATUS.labels(proc.cfg.camera_id).set(0)
                proc.process_frame(None, timestamp_s=time.time(), camera_online=False)
                break

            now = time.time()
            interval = 1.0 / max(1, proc.effective_fps)
            if (now - last_infer_s) < interval:
                # Back-pressure frame drop: skip intermediate frames beyond target_fps
                continue
            last_infer_s = now

            t0 = time.perf_counter()
            proc.process_frame(frame, timestamp_s=now, camera_online=True)
            INFERENCE_LATENCY.observe((time.perf_counter() - t0) * 1000.0)
            FRAMES_PROCESSED.labels(proc.cfg.camera_id).inc()
        cap.release()


def main() -> None:
    settings = get_cv_settings()
    signal.signal(signal.SIGTERM, lambda *_: _stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: _stop_event.set())

    _start_metrics_server(9101)
    vk = Valkey.from_url(settings.valkey_url, decode_responses=True)
    logger.info("cv_worker_started", device=settings.ml_device, demo_mode=settings.demo_mode)

    # Keep worker alive & publish heartbeats while awaiting camera configs via Valkey Pub/Sub
    ks = KillSwitchClient(vk)
    _ = (ks, CameraPipelineConfig)
    while not _stop_event.is_set():
        with contextlib.suppress(Exception):
            vk.set("tp:cv:heartbeat", str(int(time.time())), ex=30)
        _stop_event.wait(5.0)


if __name__ == "__main__":
    main()
