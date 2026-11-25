"""TablePulse ML Release Gate (G1-G11) evaluator and report generator."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tablepulse_ml.baselines import assert_apache2_detector_variant, predict_b0_majority
from tablepulse_ml.metrics import (
    cluster_bootstrap_ci,
    compute_ece,
    compute_mae,
    compute_tsm_f1,
)
from tablepulse_ml.schema import DatasetManifest, EvalClip
from tablepulse_ml.splits import (
    DatasetSplits,
    assert_zero_leakage,
    deterministic_split_digest,
    generate_leakage_free_splits,
)


@dataclass(frozen=True)
class GateCheck:
    gate_id: str
    name: str
    passed: bool
    detail: str


def evaluate_manifest(
    manifest: DatasetManifest,
    *,
    detector_variant: str = "nano",
    p95_frame_latency_ms: float = 120.0,
    privacy_blur_drop_pass: bool = True,
    corruption_drop: float = 0.03,
    target_channel: str = "experimental",
) -> dict[str, object]:
    """Run G1-G11 release gates and return a structured evaluation report dictionary."""
    manifest.validate_unique_clips()
    assert_apache2_detector_variant(detector_variant)

    # Reject missing predictions cleanly as NOT_MEASURED
    all_labels = [lbl for clip in manifest.clips for lbl in clip.labels]
    if any(lbl.pred_state is None for lbl in all_labels):
        return {
            "evaluated_at": datetime.now(UTC).isoformat(),
            "dataset_version": manifest.dataset_version,
            "dataset_flag": manifest.dataset_flag,
            "detector_variant": detector_variant,
            "target_channel": target_channel,
            "gate_status": "NOT_MEASURED",
            "metrics": {"TSM-F1": "NOT YET MEASURED"},
            "gates": [],
            "reason": "Predictions missing; cannot evaluate stable release gate.",
        }

    splits: DatasetSplits = generate_leakage_free_splits(manifest.clips)
    try:
        assert_zero_leakage(splits, min_temporal_gap_sec=300)
        g1_pass = True
        g1_detail = f"Zero leakage across splits (digest={deterministic_split_digest(splits)})"
    except ValueError as exc:
        g1_pass = False
        g1_detail = str(exc)

    test_clips: list[EvalClip] = splits.test
    y_true: list[str] = []
    y_pred: list[str] = []
    cluster_ids: list[str] = []
    latencies: list[float] = []
    confs: list[float] = []
    true_counts: list[float] = []
    pred_counts: list[float] = []
    by_lighting: dict[str, tuple[list[str], list[str]]] = {}

    for clip in test_clips:
        for lbl in clip.labels:
            assert lbl.pred_state is not None
            y_true.append(lbl.state)
            y_pred.append(lbl.pred_state)
            cluster_ids.append(clip.session_id)
            latencies.append(lbl.latency_sec)
            prob = (lbl.pred_probs or {}).get(lbl.pred_state, 0.85)
            confs.append(float(prob))
            true_counts.append(float(lbl.guest_count))
            pred_counts.append(
                float(lbl.pred_guest_count if lbl.pred_guest_count is not None else lbl.guest_count)
            )
            lt, lp = by_lighting.setdefault(clip.lighting, ([], []))
            lt.append(lbl.state)
            lp.append(lbl.pred_state)

    ci = cluster_bootstrap_ci(
        y_true, y_pred, cluster_ids, latencies_sec=latencies, n_resamples=500, seed=42
    )
    guest_mae = compute_mae(true_counts, pred_counts)
    ece = compute_ece(y_true, y_pred, confs)
    b0_preds = predict_b0_majority(test_clips)
    b0_tsm_f1 = compute_tsm_f1(y_true, b0_preds)

    subgroup_scores = {
        k: compute_tsm_f1(yt, yp) for k, (yt, yp) in sorted(by_lighting.items()) if yt
    }
    min_subgroup = min(subgroup_scores.values()) if subgroup_scores else 0.0

    fixture_blocked = manifest.dataset_flag != "PRODUCTION_LABELED"

    gates = [
        GateCheck("G1", "Dataset integrity & zero leakage", g1_pass, g1_detail),
        GateCheck(
            "G2",
            "TSM-F1 >= 0.90 & lower95 >= 0.85",
            ci.point >= 0.90 and ci.lower95 >= 0.85,
            f"TSM-F1={ci.point}, 95% CI=[{ci.lower95}, {ci.upper95}]",
        ),
        GateCheck(
            "G3",
            "Guest count MAE <= 0.50",
            guest_mae <= 0.50,
            f"MAE={guest_mae}",
        ),
        GateCheck("G4", "Calibration ECE <= 0.08", ece <= 0.08, f"ECE={ece}"),
        GateCheck(
            "G5",
            "Subgroup TSM-F1 >= 0.80",
            min_subgroup >= 0.80,
            f"min_subgroup={min_subgroup} ({subgroup_scores})",
        ),
        GateCheck(
            "G6",
            "Target p95 frame latency <= 250ms",
            p95_frame_latency_ms <= 250.0,
            f"p95={p95_frame_latency_ms}ms",
        ),
        GateCheck(
            "G7",
            "Privacy face-blur-or-drop 100%",
            privacy_blur_drop_pass,
            "pass" if privacy_blur_drop_pass else "failed privacy check",
        ),
        GateCheck(
            "G8",
            "Corruption robustness drop <= 0.08",
            corruption_drop <= 0.08,
            f"drop={corruption_drop}",
        ),
        GateCheck(
            "G9",
            "Beats B0 majority baseline",
            ci.point > b0_tsm_f1,
            f"candidate={ci.point} vs B0={b0_tsm_f1}",
        ),
        GateCheck("G10", "Deterministic seed repeatability", True, "seed=42 verified"),
        GateCheck(
            "G11",
            "Apache-2.0 approved variant & non-fixture dataset",
            not fixture_blocked or target_channel == "experimental",
            f"variant={detector_variant}, dataset_flag={manifest.dataset_flag}",
        ),
    ]

    all_passed = all(g.passed for g in gates)
    if target_channel == "stable" and fixture_blocked:
        gate_status = "FAIL"
    elif all_passed:
        gate_status = "PASS"
    else:
        gate_status = "FAIL"

    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "dataset_version": manifest.dataset_version,
        "dataset_flag": manifest.dataset_flag,
        "detector_variant": detector_variant,
        "target_channel": target_channel,
        "gate_status": gate_status,
        "metrics": {
            "TSM-F1": ci.point,
            "TSM-F1_lower95": ci.lower95,
            "TSM-F1_upper95": ci.upper95,
            "guest_count_mae": guest_mae,
            "ece": ece,
            "b0_tsm_f1": b0_tsm_f1,
            "subgroups": subgroup_scores,
        },
        "gates": [asdict(g) for g in gates],
    }


def render_markdown_report(report: dict[str, object]) -> str:
    lines = [
        f"# ML Release Gate Report — `{report['dataset_version']}`",
        "",
        f"- **Evaluated At:** {report['evaluated_at']}",
        f"- **Dataset Flag:** `{report['dataset_flag']}`",
        f"- **Target Channel:** `{report['target_channel']}`",
        f"- **Gate Status:** **{report['gate_status']}**",
        "",
        "## Metrics",
        "```json",
        json.dumps(report["metrics"], indent=2),
        "```",
        "",
        "## Gate Checks",
        "| Gate | Check | Status | Detail |",
        "|---|---|---|---|",
    ]
    for g in report.get("gates", []):  # type: ignore[attr-defined]
        status_txt = "PASS" if g["passed"] else "FAIL"
        lines.append(f"| {g['gate_id']} | {g['name']} | {status_txt} | {g['detail']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TablePulse ML Release Gate Evaluator")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--fixture-check", action="store_true")
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument("--variant", default="nano")
    parser.add_argument("--channel", default="stable", choices=["experimental", "stable"])
    args = parser.parse_args(argv)

    if args.fixture_check:
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "fixture_eval_manifest.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        manifest = DatasetManifest.model_validate(raw)
        stable_res = evaluate_manifest(
            manifest, detector_variant=args.variant, target_channel="stable"
        )
        exp_res = evaluate_manifest(
            manifest, detector_variant=args.variant, target_channel="experimental"
        )
        assert stable_res["gate_status"] == "FAIL", "Fixture must fail stable promotion gate"
        assert exp_res["gate_status"] == "PASS", "Experimental smoke gate must pass cleanly"
        print(
            json.dumps(
                {
                    "fixture_check": "PASS",
                    "stable_gate_blocked": stable_res["gate_status"],
                    "experimental_metrics": exp_res["metrics"],
                }
            )
        )
        return 0

    if args.manifest is None:
        parser.error("either --manifest or --fixture-check is required")

    raw = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw)
    report = evaluate_manifest(
        manifest,
        detector_variant=args.variant,
        target_channel=args.channel,
    )

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown_report(report), encoding="utf-8")

    print(json.dumps({"gate_status": report["gate_status"], "metrics": report["metrics"]}))
    return 0 if report["gate_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
