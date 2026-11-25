"""Mandatory face-blur-or-drop privacy filter for CV Worker."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class FaceBlurError(RuntimeError):
    """Raised when face blurring cannot be verified; caller must drop the frame."""


@lru_cache(maxsize=1)
def _load_cascades() -> list[Any]:
    cascades: list[Any] = []
    search_dirs = [
        Path(__file__).resolve().parents[2] / "infra" / "cascades",
        Path("/app/infra/cascades"),
    ]
    if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        search_dirs.insert(0, Path(cv2.data.haarcascades))
    for fname in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
        for d in search_dirs:
            p = d / fname
            if p.exists():
                clf = cv2.CascadeClassifier(str(p))
                if not clf.empty():
                    cascades.append(clf)
                    break
    if not cascades:
        raise FaceBlurError("No face detection cascades available")
    return cascades


def blur_faces_in_frame(
    frame: np.ndarray[Any, Any],
    *,
    person_boxes_px: list[tuple[int, int, int, int]] | None = None,
) -> np.ndarray[Any, Any]:
    """
    Blur detected faces (Haar cascades) AND upper-head 30% of any detected person boxes.
    Raises FaceBlurError on any error so callers drop the frame immediately.
    """
    if frame is None or frame.size == 0:
        raise FaceBlurError("Empty frame")
    try:
        cascades = _load_cascades()
        out = frame.copy()
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        h, w = out.shape[:2]

        blur_regions: list[tuple[int, int, int, int]] = []
        for clf in cascades:
            boxes = clf.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(16, 16))
            for x, y, bw, bh in boxes:
                pad_x = int(bw * 0.2)
                pad_y = int(bh * 0.2)
                blur_regions.append(
                    (
                        max(0, int(x) - pad_x),
                        max(0, int(y) - pad_y),
                        min(w, int(x + bw) + pad_x),
                        min(h, int(y + bh) + pad_y),
                    )
                )

        # Also blur upper 30% head zone of every detected person box for oblique CCTV angles
        for x1, y1, x2, y2 in person_boxes_px or []:
            bh = max(1, y2 - y1)
            hy2 = min(h, y1 + max(12, int(bh * 0.30)))
            blur_regions.append((max(0, x1), max(0, y1), min(w, x2), hy2))

        for x1, y1, x2, y2 in blur_regions:
            if x2 <= x1 or y2 <= y1:
                continue
            roi = out[y1:y2, x1:x2]
            k = max(21, (min(x2 - x1, y2 - y1) // 2) | 1)
            out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 30)

        return out
    except FaceBlurError:
        raise
    except Exception as exc:
        raise FaceBlurError(f"Face blur failed: {exc}") from exc


def encode_blurred_jpeg(
    frame: np.ndarray[Any, Any],
    *,
    person_boxes_px: list[tuple[int, int, int, int]] | None = None,
) -> bytes:
    blurred = blur_faces_in_frame(frame, person_boxes_px=person_boxes_px)
    ok, buf = cv2.imencode(".jpg", blurred, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise FaceBlurError("JPEG encode failed")
    return bytes(buf.tobytes())
