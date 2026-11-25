"""TablePulse Real Hardware Benchmark Runner -> writes docs/benchmarks.md."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import numpy as np  # noqa: E402
from evaluate_gate import evaluate_manifest  # noqa: E402
from tablepulse_ml.schema import DatasetManifest  # noqa: E402


def _load_cv_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_priv = _load_cv_module("cv_privacy", ROOT / "cv-worker" / "app" / "privacy.py")
_sm = _load_cv_module("cv_sm", ROOT / "cv-worker" / "app" / "state_machine.py")


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return round(s[idx], 2)


def main() -> int:
    frame = np.full((720, 1280, 3), 180, dtype=np.uint8)
    cv_lat_ms: list[float] = []
    sm = _sm.TableStateMachine()
    tracker = _sm.TableTrackerState(table_id="bench-t1")

    for i in range(60):
        t0 = time.perf_counter()
        _ = _priv.encode_blurred_jpeg(frame, person_boxes_px=[(120, 100, 260, 420)])
        sm.step(
            tracker,
            _sm.TableObservation(
                timestamp_s=1000.0 + i * 0.5,
                seated_guest_count=2,
                staff_at_perimeter=False,
                cleanliness_label="CLEAN",
                cleanliness_conf=0.92,
                detection_conf=0.90,
                camera_online=True,
            ),
        )
        cv_lat_ms.append((time.perf_counter() - t0) * 1000.0)

    raw = json.loads((ROOT / "ml" / "fixtures" / "fixture_eval_manifest.json").read_text())
    manifest = DatasetManifest.model_validate(raw)
    gate_lat_ms: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        _ = evaluate_manifest(manifest, detector_variant="nano", target_channel="experimental")
        gate_lat_ms.append((time.perf_counter() - t0) * 1000.0)

    now_iso = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cpu = platform.processor() or platform.machine()
    cores = os.cpu_count() or 1

    md = f"""# TablePulse Measured Benchmarks

- **Measured At:** {now_iso}
- **Host Hardware:** `{platform.system()} {platform.release()}` · `{cpu}` ({cores} logical cores)
- **Execution Mode:** CPU reference path (`cv-worker` OpenCV + state machine; `ml` release gate)
- **Model Accuracy Note:** **TSM-F1 and Guest Count MAE remain `NOT YET MEASURED`** on production restaurant CCTV footage because real labelled multi-venue datasets do not ship in this repository. Only real runtime latency & gate overhead are reported below.

| Workload | Iterations | Mean (ms) | p50 (ms) | p95 (ms) | Notes |
|---|---|---|---|---|---|
| 720p Frame Face-Blur + JPEG Encode + State Step | {len(cv_lat_ms)} | {round(statistics.mean(cv_lat_ms), 2)} | {percentile(cv_lat_ms, 50)} | {percentile(cv_lat_ms, 95)} | CPU OpenCV Haar cascade + upper-head blur + deterministic state tracker |
| ML Release Gate (`G1–G11` + 500-resample cluster bootstrap) | {len(gate_lat_ms)} | {round(statistics.mean(gate_lat_ms), 2)} | {percentile(gate_lat_ms, 50)} | {percentile(gate_lat_ms, 95)} | Over synthetic fixture `tablepulse-fixture-v1` |
"""
    out_path = ROOT / "docs" / "benchmarks.md"
    out_path.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
