# Model Card — `tablepulse-detector-b1@0.1.0`

- **Model Role:** `DETECTOR` (Person & Table Surface State Estimator)
- **Architecture:** Apache-2.0 **RF-DETR Nano** (zero-shot ONNX baseline) + ByteTrack (`supervision` MIT) + deterministic debounce state machine (`cv-worker/app/state_machine.py`)
- **Channel:** `experimental`
- **License:** Apache-2.0 (strictly verified; Roboflow Platform Model License variants `Atto/Femto/Pico/XL/2XL` and AGPL `ultralytics` are never used)
- **Measured Offline TSM-F1:** **NOT YET MEASURED**
- **Measured Guest Count MAE:** **NOT YET MEASURED**
- **Measured Calibration ECE:** **NOT YET MEASURED**
- **Known Limitations:**
  - The 90%–95% TSM-F1 release target requires fine-tuning on real multi-venue, privacy-blurred annotated restaurant CCTV data that the repository maintainers do not ship.
  - Because `gate_status` is `NOT_MEASURED`, `POST /api/v1/org/system/models/{id}/activate` refuses promotion to `channel=stable` (`409 VERSION_CONFLICT`).
- **Privacy Safeguards:** Operates exclusively on transient in-memory frames after mandatory Haar/blurred face anonymization; drops any frame where face detection/blur raises an error. Audio streams are stripped at ingest.
