"""Normalized (0.0-1.0) polygon validation and self-intersection checks."""

from __future__ import annotations

from collections.abc import Sequence


def _ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    d1 = _ccw(*p3, *p4, *p1)
    d2 = _ccw(*p3, *p4, *p2)
    d3 = _ccw(*p1, *p2, *p3)
    d4 = _ccw(*p1, *p2, *p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True

    def _on_seg(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(
            a[1], b[1]
        )

    if d1 == 0 and _on_seg(p3, p4, p1):
        return True
    if d2 == 0 and _on_seg(p3, p4, p2):
        return True
    if d3 == 0 and _on_seg(p1, p2, p3):
        return True
    return bool(d4 == 0 and _on_seg(p1, p2, p4))


def polygon_area(points: Sequence[tuple[float, float]]) -> float:
    """Shoelace area of a 2D polygon."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def validate_normalized_polygon(vertices: Sequence[dict[str, float]]) -> str | None:
    """
    Validate polygon vertices:
    - >= 3 vertices
    - coordinates within [0.0, 1.0]
    - non-degenerate area (> 1e-5)
    - no non-adjacent edge self-intersections
    Returns error reason string if invalid, else None.
    """
    if len(vertices) < 3:
        return "polygon must have at least 3 vertices"

    pts: list[tuple[float, float]] = []
    for v in vertices:
        x = float(v["x"])
        y = float(v["y"])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return "all polygon coordinates must be normalized between 0.0 and 1.0"
        pts.append((x, y))

    if polygon_area(pts) < 1e-5:
        return "polygon area is too small or collinear"

    n = len(pts)
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            # Adjacent edges share a vertex; wrap-around (0, n-1) also shares vertex 0
            if j == i or j == (i + 1) % n or (i == 0 and j == n - 1):
                continue
            b1, b2 = pts[j], pts[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return "polygon edges must not self-intersect"
    return None
