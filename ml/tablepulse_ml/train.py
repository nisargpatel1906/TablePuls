"""Detector & ETA training config validator and Apache-2.0 trainer entrypoints."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from tablepulse_ml.baselines import assert_apache2_detector_variant


def load_training_config(config_path: Path) -> dict[str, object]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid YAML training config")
    variant = str(raw.get("rfdetr_variant", ""))
    assert_apache2_detector_variant(variant)
    return raw
