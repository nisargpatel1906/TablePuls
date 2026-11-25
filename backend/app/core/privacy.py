"""Privacy-by-design face-blurring utility (blur-or-drop rule, AGENTS.md §6)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class FaceBlurError(RuntimeError):
    """Raised when face blurring fails so caller MUST drop the frame."""


@lru_cache(maxsize=1)
def _load_cascades() -> list[Any]:
    cascades: list[Any] = []
    search_dirs = [
        Path(cv2.data.haarcascades),  # type: ignore[attr-defined]
        Path(__file__).resolve().parents[3] / "infra" / "cascades",
        Path("/app/infra/cascades"),
    ]
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


def blur_faces_in_bgr(frame: np.ndarray[Any, Any]) -> bytes:
    """
    Detect and Gaussian-blur all face regions in a BGR frame, returning JPEG bytes.
    Raises FaceBlurError on any error so callers drop the frame rather than emit unblurred video.
    """
    if frame is None or frame.size == 0:
        raise FaceBlurError("Empty frame")
    try:
        cascades = _load_cascades()
        out = frame.copy()
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        h, w = out.shape[:2]

        for clf in cascades:
            boxes = clf.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
            for x, y, bw, bh in boxes:
                pad_x = int(bw * 0.15)
                pad_y = int(bh * 0.15)
                x1 = max(0, int(x) - pad_x)
                y1 = max(0, int(y) - pad_y)
                x2 = min(w, int(x + bw) + pad_x)
                y2 = min(h, int(y + bh) + pad_y)
                if x2 <= x1 or y2 <= y1:
                    continue
                roi = out[y1:y2, x1:x2]
                k = max(21, (min(bw, bh) // 2) | 1)
                out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 30)

        ok, encoded = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise FaceBlurError("JPEG encoding failed")
        return bytes(encoded.tobytes())
    except FaceBlurError:
        raise
    except Exception as exc:
        raise FaceBlurError(f"Face blur failed: {exc}") from exc


def generate_demo_floor_frame(
    width: int = 1280, height: int = 720
) -> np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]:
    """Render a clean synthetic restaurant floor frame (>= 640x480) when demo MP4 is absent."""
    img = np.full((height, width, 3), (38, 42, 48), dtype=np.uint8)
    # Draw floor grid and 4 stylized tables
    for x in range(0, width, 80):
        cv2.line(img, (x, 0), (x, height), (50, 55, 62), 1)
    for y in range(0, height, 80):
        cv2.line(img, (0, y), (width, y), (50, 55, 62), 1)
    tables = [
        ("T01", (220, 180, 380, 300), (60, 140, 80)),
        ("T02", (540, 180, 720, 300), (60, 70, 170)),
        ("T03", (880, 180, 1060, 300), (60, 140, 80)),
        ("T04", (380, 440, 620, 580), (40, 130, 190)),
    ]
    for label, (x1, y1, x2, y2), color in tables:
        cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (220, 225, 230), 2)
        cv2.putText(
            img, label, (x1 + 18, y1 + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2
        )
    cv2.putText(
        img,
        "TABLEPULSE DEMO STREAM (AUDIO STRIPPED | FACE BLUR ON)",
        (24, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (230, 235, 240),
        2,
    )
    return img
