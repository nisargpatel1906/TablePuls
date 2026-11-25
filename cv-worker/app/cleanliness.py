"""Table cleanliness classifier (ConvNeXt-Tiny / MobileNetV3 ONNX + edge-density fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(slots=True)
class CleanlinessPrediction:
    label: str  # "CLEAN" | "DIRTY" | "UNKNOWN"
    confidence: float


class CleanlinessClassifier:
    def __init__(self, onnx_path: Path | None = None, device: str = "cpu") -> None:
        self.session: Any = None
        if onnx_path is not None and onnx_path.exists():
            import onnxruntime as ort

            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if device.startswith("cuda")
                else ["CPUExecutionProvider"]
            )
            self.session = ort.InferenceSession(str(onnx_path), providers=providers)

    def classify_crop(self, crop_bgr: np.ndarray[Any, Any]) -> CleanlinessPrediction:
        if crop_bgr is None or crop_bgr.size == 0:
            return CleanlinessPrediction(label="UNKNOWN", confidence=0.0)

        if self.session is not None:
            rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (224, 224)).astype(np.float32) / 255.0
            inp = np.transpose(resized, (2, 0, 1))[None, ...]
            input_name = self.session.get_inputs()[0].name
            logits = self.session.run(None, {input_name: inp})[0][0]
            probs = np.exp(logits - np.max(logits))
            probs = probs / np.sum(probs)
            dirty_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
            if dirty_prob >= 0.5:
                return CleanlinessPrediction(label="DIRTY", confidence=dirty_prob)
            return CleanlinessPrediction(label="CLEAN", confidence=1.0 - dirty_prob)

        # Deterministic surface clutter fallback using Canny edge density on tabletop ROI
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 150)
        edge_ratio = float(np.mean(edges > 0))
        if edge_ratio > 0.08:
            return CleanlinessPrediction(label="DIRTY", confidence=min(0.95, 0.65 + edge_ratio))
        return CleanlinessPrediction(label="CLEAN", confidence=max(0.70, 0.95 - edge_ratio * 2.0))
