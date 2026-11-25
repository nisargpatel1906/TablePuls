"""ML evaluation harness test suite (docs/07 §12)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluate_gate import evaluate_manifest
from tablepulse_ml.baselines import assert_apache2_detector_variant
from tablepulse_ml.metrics import (
    cluster_bootstrap_ci,
    compute_ece,
    compute_tsm_f1,
    paired_cluster_bootstrap_delta,
)
from tablepulse_ml.schema import DatasetManifest
from tablepulse_ml.splits import DatasetSplits, assert_zero_leakage, generate_leakage_free_splits
from tablepulse_ml.train import load_training_config


def _load_fixture() -> DatasetManifest:
    p = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_eval_manifest.json"
    return DatasetManifest.model_validate(json.loads(p.read_text(encoding="utf-8")))


def test_schema_validation_rejects_invalid_state() -> None:
    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "fixture_eval_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    raw["clips"][0]["labels"][0]["state"] = "BOGUS_STATE"
    with pytest.raises(ValidationError):
        DatasetManifest.model_validate(raw)


def test_split_leakage_five_invariants() -> None:
    m = _load_fixture()
    splits = generate_leakage_free_splits(m.clips, min_temporal_gap_sec=300)
    assert len(splits.train) >= 1 and len(splits.val) >= 1 and len(splits.test) >= 1

    # Corrupt a split with duplicate session_id -> must raise
    bad = DatasetSplits(train=splits.train, val=splits.val, test=[splits.train[0], *splits.test])
    with pytest.raises(ValueError, match="leakage"):
        assert_zero_leakage(bad)


def test_metrics_tsm_f1_bootstrap_and_ece() -> None:
    y_true = ["FREE", "OCCUPIED", "NEEDS_CLEANING", "NEEDS_SERVICE"] * 3
    y_pred = ["FREE", "OCCUPIED", "NEEDS_CLEANING", "NEEDS_SERVICE"] * 3
    assert compute_tsm_f1(y_true, y_pred, latencies_sec=[1.0] * len(y_true)) == 1.0
    # High latency penalizes TSM-F1
    penalized = compute_tsm_f1(y_true, y_pred, latencies_sec=[5.0] * len(y_true))
    assert penalized < 1.0

    ci = cluster_bootstrap_ci(
        y_true, y_pred, [f"s{i // 4}" for i in range(len(y_true))], n_resamples=200, seed=42
    )
    assert ci.lower95 == 1.0 and ci.upper95 == 1.0

    ece = compute_ece(y_true, y_pred, [0.95] * len(y_true))
    assert ece == 0.05

    paired = paired_cluster_bootstrap_delta(
        y_true,
        ["FREE"] * len(y_true),
        y_pred,
        [f"s{i // 4}" for i in range(len(y_true))],
        n_resamples=100,
    )
    assert paired["delta"] > 0.5


def test_release_gate_blocks_fixture_unmeasured_and_banned_variants() -> None:
    m = _load_fixture()
    # Promoting FIXTURE-NOT-FOR-REPORTING dataset to stable must FAIL
    res_fixture = evaluate_manifest(m, detector_variant="nano", target_channel="stable")
    assert res_fixture["gate_status"] == "FAIL"

    # Experimental synthetic smoke check can pass technical gates if dataset_flag=PRODUCTION_LABELED
    prod_like = m.model_copy(update={"dataset_flag": "PRODUCTION_LABELED"})
    res_pass = evaluate_manifest(prod_like, detector_variant="nano", target_channel="stable")
    assert res_pass["gate_status"] == "PASS"

    # Below-threshold TSM-F1 (< 0.90) must FAIL
    corrupted = prod_like.model_copy(deep=True)
    for c in corrupted.clips:
        for lbl in c.labels:
            lbl.pred_state = "FREE"
    res_low = evaluate_manifest(corrupted, detector_variant="nano", target_channel="stable")
    assert res_low["gate_status"] == "FAIL"

    # Missing predictions -> NOT_MEASURED
    unmeasured = prod_like.model_copy(deep=True)
    unmeasured.clips[0].labels[0].pred_state = None
    res_nm = evaluate_manifest(unmeasured, detector_variant="nano", target_channel="stable")
    assert res_nm["gate_status"] == "NOT_MEASURED"
    assert res_nm["metrics"]["TSM-F1"] == "NOT YET MEASURED"  # type: ignore[index]

    # License ban check on Roboflow PML / AGPL variants
    for banned in ("atto", "xl", "2xl", "ultralytics"):
        with pytest.raises(ValueError, match="Banned"):
            assert_apache2_detector_variant(banned)

    cfg = load_training_config(
        Path(__file__).resolve().parents[1] / "configs" / "detector_rfdetr_nano.yaml"
    )
    assert cfg["rfdetr_variant"] == "nano"
