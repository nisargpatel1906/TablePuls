# TablePulse Measured Benchmarks

- **Measured At:** 2026-11-25 10:17 UTC
- **Host Hardware:** `Windows 11` · `Intel64 Family 6 Model 183 Stepping 1, GenuineIntel` (16 logical cores)
- **Execution Mode:** CPU reference path (`cv-worker` OpenCV + state machine; `ml` release gate)
- **Model Accuracy Note:** **TSM-F1 and Guest Count MAE remain `NOT YET MEASURED`** on production restaurant CCTV footage because real labelled multi-venue datasets do not ship in this repository. Only real runtime latency & gate overhead are reported below.

| Workload | Iterations | Mean (ms) | p50 (ms) | p95 (ms) | Notes |
|---|---|---|---|---|---|
| 720p Frame Face-Blur + JPEG Encode + State Step | 60 | 313.17 | 233.12 | 501.12 | CPU OpenCV Haar cascade + upper-head blur + deterministic state tracker |
| ML Release Gate (`G1–G11` + 500-resample cluster bootstrap) | 10 | 0.71 | 0.61 | 1.07 | Over synthetic fixture `tablepulse-fixture-v1` |
