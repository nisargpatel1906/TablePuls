# TablePulse Privacy-by-Design Controls

1. **Zero Biometrics & Zero Audio:** MediaMTX strips audio tracks at ingestion (`mediamtx.yml`). TablePulse never extracts face embeddings, demographic attributes, cross-visit IDs, or individual employee scores.
2. **Ephemeral Video Frames:** Camera frames are decoded strictly in memory at 1–5 FPS. Raw video streams are never written to disk by the backend or CV worker.
3. **Mandatory Face Blur-or-Drop (`privacy.py`):** Whenever a snapshot preview or ML review crop is encoded, OpenCV Haar cascades (`infra/cascades/haarcascade_*.xml`) detect and Gaussian-blur all face regions **and upper-person head zones** before JPEG encoding. If blurring raises an error, the frame is immediately **dropped** (`FaceBlurError`).
4. **Fail-Closed Kill Switches:** Missing or unreachable `AI_INFERENCE_ENABLED`, `WEBHOOKS_ENABLED`, or `REVIEW_CROPS_ENABLED` default strictly to `false` (paused).
5. **Bounded Retention & Immediate Purge:** Temporary review crops expire via `snapshot_retention_days` (default: `7` days) and can be deleted immediately by `OWNER` via `POST /api/v1/org/system/purge-snapshots` (`SCR-016`).
