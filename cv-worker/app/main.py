"""CV Worker runtime loop, health/metrics server (:9101), camera sync, and back-pressure frame dropper."""

from __future__ import annotations

import contextlib
import hashlib
import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import cv2
import httpx
import structlog
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from valkey import Valkey

from app.config import get_cv_settings
from app.state_machine import TableRuleConfig
from app.worker import CameraPipelineConfig, CameraProcessor, KillSwitchClient, TableROI

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


def _run_camera_loop(proc: CameraProcessor, stop_flag: threading.Event | None = None) -> None:
    """Process frames from RTSP/Demo MP4 with exponential reconnect and 1x-paced sampling."""
    backoff = 1.0
    cap: Any = None
    settings = get_cv_settings()
    local_stop = stop_flag or _stop_event

    while not _stop_event.is_set() and not local_stop.is_set():
        src = proc.cfg.stream_url
        if proc.cfg.stream_type == "DEMO_MP4":
            demo_root = Path(settings.demo_video_path).resolve().parent
            cand = Path(src).resolve() if src and not src.startswith("demo://") else None
            if cand is not None and cand.is_relative_to(demo_root) and cand.is_file():
                src = str(cand)
            else:
                src = settings.demo_video_path
        if proc.cfg.stream_type == "DEMO_MP4" and not Path(src).exists():
            time.sleep(2.0)
            continue

        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            CAMERA_STATUS.labels(proc.cfg.camera_id).set(0)
            proc.process_frame(None, timestamp_s=time.time(), camera_online=False)
            local_stop.wait(backoff)
            backoff = min(60.0, backoff * 2.0)
            continue

        backoff = 1.0
        CAMERA_STATUS.labels(proc.cfg.camera_id).set(1)
        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if src_fps <= 0.1 or src_fps > 120.0:
            src_fps = 15.0
        last_infer_s = 0.0

        while not _stop_event.is_set() and not local_stop.is_set():
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
                if proc.cfg.stream_type == "DEMO_MP4":
                    local_stop.wait(max(0.02, min(interval - (now - last_infer_s), 1.0 / src_fps)))
                continue
            last_infer_s = now

            t0 = time.perf_counter()
            proc.process_frame(frame, timestamp_s=now, camera_online=True)
            INFERENCE_LATENCY.observe((time.perf_counter() - t0) * 1000.0)
            FRAMES_PROCESSED.labels(proc.cfg.camera_id).inc()
        cap.release()


def _parse_camera_config(raw: dict[str, Any]) -> CameraPipelineConfig:
    tables: list[TableROI] = []
    for t in raw.get("tables", []):
        poly = list(t.get("polygon_json") or [])
        if len(poly) < 3:
            continue
        r = t.get("rules", {})
        tables.append(
            TableROI(
                table_id=str(t["table_id"]),
                table_code=str(t["table_code"]),
                venue_id=str(t["venue_id"]),
                organization_id=str(t["organization_id"]),
                polygon=poly,
                rules=TableRuleConfig(
                    occupancy_debounce_sec=float(r.get("occupancy_debounce_sec", 10)),
                    departure_debounce_sec=float(r.get("departure_debounce_sec", 20)),
                    unattended_service_sec=float(r.get("unattended_service_sec", 300)),
                    cleaning_alert_delay_sec=float(r.get("cleaning_alert_delay_sec", 120)),
                    min_confidence=float(r.get("min_confidence", 0.65)),
                    require_bussing_confirmation=bool(
                        r.get("require_bussing_confirmation", False)
                    ),
                ),
            )
        )
    return CameraPipelineConfig(
        camera_id=str(raw["camera_id"]),
        venue_id=str(raw["venue_id"]),
        organization_id=str(raw["organization_id"]),
        stream_url=str(raw["stream_url"]),
        stream_type=str(raw["stream_type"]),
        target_fps=int(raw.get("target_fps", 2)),
        face_blur_enabled=bool(raw.get("face_blur_enabled", True)),
        exclusion_polygons=list(raw.get("exclusion_polygons_json", [])),
        tables=tables,
    )


def _fetch_camera_configs() -> list[dict[str, Any]]:
    settings = get_cv_settings()
    url = f"{settings.api_internal_url.rstrip('/')}/api/v1/internal/cv-cameras"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers={"X-Internal-Secret": settings.mediamtx_hook_secret})
        if resp.status_code == 200:
            return list(resp.json().get("data", {}).get("cameras", []))
    except Exception as exc:
        logger.warning("cv_camera_sync_failed", error=str(exc))
    return []


def main() -> None:
    settings = get_cv_settings()
    signal.signal(signal.SIGTERM, lambda *_: _stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: _stop_event.set())

    _start_metrics_server(9101)
    vk = Valkey.from_url(settings.valkey_url, decode_responses=True)
    ks = KillSwitchClient(vk)
    logger.info("cv_worker_started", device=settings.ml_device, demo_mode=settings.demo_mode)

    active_workers: dict[str, tuple[str, threading.Event, threading.Thread]] = {}
    sync_needed = threading.Event()
    sync_needed.set()

    def _pubsub_listener() -> None:
        vk_any: Any = vk
        while not _stop_event.is_set():
            try:
                ps = vk_any.pubsub()
                ps.subscribe("tp:cv:control")
                for msg in ps.listen():
                    if _stop_event.is_set():
                        break
                    if msg.get("type") == "message":
                        sync_needed.set()
            except Exception:
                _stop_event.wait(2.0)

    threading.Thread(target=_pubsub_listener, daemon=True).start()

    last_sync_s = 0.0
    while not _stop_event.is_set():
        with contextlib.suppress(Exception):
            vk.set("tp:cv:heartbeat", str(int(time.time())), ex=30)

        now = time.time()
        if sync_needed.is_set() or (now - last_sync_s) >= 20.0:
            sync_needed.clear()
            last_sync_s = now
            raw_cams = _fetch_camera_configs()
            seen_ids: set[str] = set()
            for raw in raw_cams:
                cid = str(raw["camera_id"])
                seen_ids.add(cid)
                sig_payload = json.dumps(raw, sort_keys=True)
                cfg_hash = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()
                cur = active_workers.get(cid)
                if cur is not None and cur[0] == cfg_hash and cur[2].is_alive():
                    continue
                if cur is not None:
                    cur[1].set()
                cam_cfg = _parse_camera_config(raw)
                proc = CameraProcessor(cam_cfg, kill_switch=ks, valkey_client=vk)
                cam_stop = threading.Event()
                t = threading.Thread(target=_run_camera_loop, args=(proc, cam_stop), daemon=True)
                t.start()
                active_workers[cid] = (cfg_hash, cam_stop, t)
                logger.info(
                    "cv_camera_pipeline_started",
                    camera_id=cid,
                    stream_type=cam_cfg.stream_type,
                    tables=len(cam_cfg.tables),
                    using_onnx=proc.detector.using_onnx,
                )

            for cid in list(active_workers.keys()):
                if cid not in seen_ids:
                    active_workers[cid][1].set()
                    active_workers.pop(cid, None)

        _stop_event.wait(5.0)

    for _, cam_stop, _ in active_workers.values():
        cam_stop.set()


if __name__ == "__main__":
    main()
