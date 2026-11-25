"""RF-DETR (Apache-2.0 Nano/Small/Medium/Large ONLY) ONNX detector + B1 zero-shot fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ALLOWED_RFDETR_SIZES = {"nano", "small", "medium", "large"}
BANNED_RFDETR_SIZES = {"atto", "femto", "pico", "xl", "2xl", "xlarge", "2xlarge"}


@dataclass(slots=True)
class Detection:
    x1: float  # normalized 0..1
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str  # "person" | "tableware"


class DetectorError(RuntimeError):
    """Raised when detector configuration violates license policy or fails."""


class PersonAndObjectDetector:
    """
    Loads an Apache-2.0 RF-DETR ONNX model (Nano/Small/Medium/Large ONLY).
    Falls back to a deterministic OpenCV HOG person detector (Baseline B1 zero-shot,
    experimental) if no ONNX weights file is mounted.
    """

    def __init__(
        self,
        model_variant: str = "nano",
        onnx_path: Path | None = None,
        device: str = "cpu",
    ) -> None:
        variant_l = model_variant.strip().lower()
        if variant_l in BANNED_RFDETR_SIZES or variant_l not in ALLOWED_RFDETR_SIZES:
            raise DetectorError(
                f"Model variant '{model_variant}' is banned by Apache-2.0 license policy; "
                "allowed variants: nano, small, medium, large"
            )
        self.model_variant = variant_l
        self.device = device
        self.session: Any = None
        self.using_onnx = False

        if onnx_path is not None and onnx_path.exists():
            import onnxruntime as ort

            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if device.startswith("cuda")
                else ["CPUExecutionProvider"]
            )
            self.session = ort.InferenceSession(str(onnx_path), providers=providers)
            self.using_onnx = True
        else:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())  # type: ignore[attr-defined]

    def detect(
        self, frame: np.ndarray[Any, Any], *, conf_threshold: float = 0.40
    ) -> list[Detection]:
        if frame is None or frame.size == 0:
            return []
        h, w = frame.shape[:2]
        if w <= 0 or h <= 0:
            return []

        if self.using_onnx and self.session is not None:
            return self._infer_onnx(frame, w, h, conf_threshold)
        return self._infer_hog_zero_shot(frame, w, h, conf_threshold)

    def _infer_onnx(
        self, frame: np.ndarray[Any, Any], w: int, h: int, conf_threshold: float
    ) -> list[Detection]:
        input_meta = self.session.get_inputs()[0]
        input_name = input_meta.name
        shape = input_meta.shape
        ih = int(shape[2]) if len(shape) >= 4 and isinstance(shape[2], int) else 384
        iw = int(shape[3]) if len(shape) >= 4 and isinstance(shape[3], int) else 384

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (iw, ih)).astype(np.float32) / 255.0

        # RF-DETR ONNX expects 91-class COCO logits and ImageNet normalization
        outputs = None
        if len(self.session.get_outputs()) >= 2 and self.session.get_outputs()[1].shape[-1] == 91:
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            resized = (resized - mean) / std
            inp = np.transpose(resized, (2, 0, 1))[None, ...].astype(np.float32)
            boxes_raw, logits_raw = self.session.run(None, {input_name: inp})
            probs = 1.0 / (1.0 + np.exp(-np.clip(logits_raw[0], -40.0, 40.0)))
            boxes = boxes_raw[0]
            # COCO 1-indexed classes in RF-DETR: 1=person; tableware={44:bottle,46:wine glass,47:cup,48:fork,49:knife,50:spoon,51:bowl}
            tableware_ids = {44, 46, 47, 48, 49, 50, 51}
            detections: list[Detection] = []
            for idx, prob_row in enumerate(probs):
                cls_idx = int(np.argmax(prob_row))
                conf = float(prob_row[cls_idx])
                if conf < conf_threshold:
                    continue
                if cls_idx == 1:
                    cls_name = "person"
                elif cls_idx in tableware_ids:
                    cls_name = "tableware"
                else:
                    continue
                cx, cy, bw, bh = [float(c) for c in boxes[idx][:4]]
                x1 = float(np.clip(cx - bw / 2.0, 0.0, 1.0))
                y1 = float(np.clip(cy - bh / 2.0, 0.0, 1.0))
                x2 = float(np.clip(cx + bw / 2.0, 0.0, 1.0))
                y2 = float(np.clip(cy + bh / 2.0, 0.0, 1.0))
                if x2 > x1 and y2 > y1:
                    detections.append(
                        Detection(
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                            confidence=conf,
                            class_name=cls_name,
                        )
                    )
            return detections

        inp = np.transpose(resized, (2, 0, 1))[None, ...]
        outputs = self.session.run(None, {input_name: inp})
        boxes = outputs[0][0]
        scores = outputs[1][0]
        detections = []
        for idx, score_row in enumerate(scores):
            conf = float(np.max(score_row))
            if conf < conf_threshold:
                continue
            cls_idx = int(np.argmax(score_row))
            cls_name = "person" if cls_idx == 0 else "tableware"
            bx1, by1, bx2, by2 = [float(np.clip(c, 0.0, 1.0)) for c in boxes[idx][:4]]
            detections.append(
                Detection(
                    x1=bx1,
                    y1=by1,
                    x2=bx2,
                    y2=by2,
                    confidence=conf,
                    class_name=cls_name,
                )
            )
        return detections

    def _infer_hog_zero_shot(
        self, frame: np.ndarray[Any, Any], w: int, h: int, conf_threshold: float
    ) -> list[Detection]:
        rects, weights = self._hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        detections: list[Detection] = []
        for (rx, ry, rw, rh), weight in zip(rects, weights, strict=False):
            conf = float(min(0.99, max(0.0, 0.5 + 0.25 * float(weight))))
            if conf < conf_threshold:
                continue
            detections.append(
                Detection(
                    x1=max(0.0, rx / w),
                    y1=max(0.0, ry / h),
                    x2=min(1.0, (rx + rw) / w),
                    y2=min(1.0, (ry + rh) / h),
                    confidence=conf,
                    class_name="person",
                )
            )
        return detections
