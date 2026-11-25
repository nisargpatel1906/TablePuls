"""Generates a clean synthetic restaurant floor MP4 video for Demo Mode (--profile demo)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.config import get_cv_settings


def generate_demo_mp4(output_path: Path, *, duration_sec: int = 12, fps: int = 2) -> Path:
    """Create a 1280x720 synthetic restaurant floor clip showing occupancy & cleaning transitions."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(output_path), fourcc, float(fps), (1280, 720))

    total_frames = duration_sec * fps
    for idx in range(total_frames):
        frame = np.full((720, 1280, 3), (38, 42, 48), dtype=np.uint8)
        for x in range(0, 1280, 80):
            cv2.line(frame, (x, 0), (x, 720), (50, 55, 62), 1)
        for y in range(0, 720, 80):
            cv2.line(frame, (0, y), (1280, y), (50, 55, 62), 1)

        tables = [
            ("T01", (160, 140, 360, 280), (55, 145, 75)),
            ("T02", (520, 140, 740, 280), (60, 65, 175)),
            ("T03", (880, 140, 1100, 280), (55, 145, 75)),
            ("T04", (420, 420, 680, 580), (45, 130, 195)),
        ]
        for label, (x1, y1, x2, y2), color in tables:
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (225, 230, 235), 2)
            cv2.putText(
                frame, label, (x1 + 20, y1 + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2
            )

        # Draw stylized synthetic guest circles at T02
        cv2.circle(frame, (570, 210), 22, (200, 200, 220), -1)
        cv2.circle(frame, (690, 210), 22, (200, 200, 220), -1)
        # Animated passerby in aisle
        px = int(120 + (idx / max(1, total_frames)) * 960)
        cv2.circle(frame, (px, 350), 20, (190, 215, 240), -1)

        cv2.putText(
            frame,
            f"TABLEPULSE DEMO CLIP | FRAME {idx + 1}/{total_frames}",
            (24, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (235, 240, 245),
            2,
        )
        writer.write(frame)
    writer.release()
    return output_path


def main() -> None:
    out = Path(get_cv_settings().demo_video_path)
    generate_demo_mp4(out)
    print(f"Generated synthetic demo video at {out}")


if __name__ == "__main__":
    main()
