"""Honest baseline predictors (B0-B3) and variant license guard."""

from __future__ import annotations

from tablepulse_ml.schema import EvalClip

APPROVED_RFDETR_VARIANTS = frozenset({"nano", "small", "medium", "large"})
BANNED_MODEL_TOKENS = frozenset(
    {"ultralytics", "yolo", "atto", "femto", "pico", "xl", "2xl", "boxmot"}
)


def assert_apache2_detector_variant(variant: str) -> str:
    """Enforce AGENTS.md §3 strict Apache-2.0 detector model policy."""
    v = variant.strip().lower()
    if any(tok in v for tok in BANNED_MODEL_TOKENS) or v not in APPROVED_RFDETR_VARIANTS:
        raise ValueError(
            f"Banned or unapproved detector variant '{variant}'. "
            f"Only Apache-2.0 RF-DETR {sorted(APPROVED_RFDETR_VARIANTS)} are allowed."
        )
    return v


def predict_b0_majority(clips: list[EvalClip]) -> list[str]:
    """B0 Majority-Class baseline (always predicts FREE)."""
    return ["FREE" for clip in clips for _ in clip.labels]


def predict_b1_zero_shot_manifest(clips: list[EvalClip]) -> list[str]:
    """B1 Zero-shot manifest baseline: emits recorded pred_state or UNKNOWN if absent."""
    preds: list[str] = []
    for clip in clips:
        for lbl in clip.labels:
            preds.append(lbl.pred_state or "UNKNOWN")
    return preds
