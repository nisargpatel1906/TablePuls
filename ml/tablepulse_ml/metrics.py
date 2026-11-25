"""Primary ML evaluation metrics: TSM-F1, cluster bootstrap CI, ECE, MAE, and paired tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EVAL_STATES = ("FREE", "OCCUPIED", "NEEDS_SERVICE", "NEEDS_CLEANING")


@dataclass(frozen=True)
class BootstrapCI:
    point: float
    lower95: float
    upper95: float


def compute_tsm_f1(
    y_true: list[str],
    y_pred: list[str],
    latencies_sec: list[float] | None = None,
    latency_budget_sec: float = 2.0,
) -> float:
    """Compute Latency-Compensated Table-State Macro-F1 across active state classes."""
    if not y_true or len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be non-empty equal-length sequences")

    present_classes = [c for c in EVAL_STATES if c in y_true]
    if not present_classes:
        present_classes = sorted(set(y_true))

    f1_scores: list[float] = []
    for cls in present_classes:
        tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == cls and p != cls)
        denom = (2 * tp) + fp + fn
        f1 = (2.0 * tp) / denom if denom > 0 else 0.0
        f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores)

    if latencies_sec:
        penalties = [
            max(0.0, 1.0 - max(0.0, lat - latency_budget_sec) * 0.1) for lat in latencies_sec
        ]
        latency_factor = sum(penalties) / len(penalties)
        macro_f1 *= latency_factor

    return round(macro_f1, 4)


def compute_ece(
    y_true: list[str],
    y_pred: list[str],
    confidences: list[float],
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error across confidence bins [0, 1]."""
    if not y_true or not (len(y_true) == len(y_pred) == len(confidences)):
        raise ValueError("Sequence lengths must match and be non-empty")

    n = len(y_true)
    ece = 0.0
    for b in range(n_bins):
        lo = b / n_bins
        hi = (b + 1) / n_bins
        indices = [
            i
            for i, c in enumerate(confidences)
            if (c >= lo and c < hi) or (b == n_bins - 1 and c == 1.0)
        ]
        if not indices:
            continue
        acc = sum(1.0 for i in indices if y_true[i] == y_pred[i]) / len(indices)
        conf = sum(confidences[i] for i in indices) / len(indices)
        ece += (len(indices) / n) * abs(acc - conf)
    return round(float(ece), 4)


def compute_mae(y_true: list[float], y_pred: list[float]) -> float:
    if not y_true or len(y_true) != len(y_pred):
        raise ValueError("MAE requires equal-length non-empty sequences")
    errs = [abs(t - p) for t, p in zip(y_true, y_pred, strict=True)]
    return round(float(sum(errs) / len(errs)), 4)


def cluster_bootstrap_ci(
    y_true: list[str],
    y_pred: list[str],
    cluster_ids: list[str],
    latencies_sec: list[float] | None = None,
    *,
    n_resamples: int = 1000,
    seed: int = 42,
) -> BootstrapCI:
    """Cluster-bootstrapped 95% confidence interval grouped by session/clip ID."""
    if not y_true or not (len(y_true) == len(y_pred) == len(cluster_ids)):
        raise ValueError("y_true, y_pred, and cluster_ids must match")

    point = compute_tsm_f1(y_true, y_pred, latencies_sec=latencies_sec)
    groups: dict[str, list[int]] = {}
    for idx, cid in enumerate(cluster_ids):
        groups.setdefault(cid, []).append(idx)
    cluster_keys = sorted(groups.keys())
    k = len(cluster_keys)
    if k <= 1:
        return BootstrapCI(point=point, lower95=point, upper95=point)

    rng = np.random.default_rng(seed)
    scores = np.empty(n_resamples, dtype=np.float64)
    for r in range(n_resamples):
        sampled = rng.integers(0, k, size=k)
        idxs: list[int] = []
        for s_idx in sampled:
            idxs.extend(groups[cluster_keys[int(s_idx)]])
        yt = [y_true[i] for i in idxs]
        yp = [y_pred[i] for i in idxs]
        lat = [latencies_sec[i] for i in idxs] if latencies_sec else None
        scores[r] = compute_tsm_f1(yt, yp, latencies_sec=lat)

    lo = float(np.percentile(scores, 2.5))
    hi = float(np.percentile(scores, 97.5))
    return BootstrapCI(point=point, lower95=round(lo, 4), upper95=round(hi, 4))


def paired_cluster_bootstrap_delta(
    y_true: list[str],
    pred_baseline: list[str],
    pred_candidate: list[str],
    cluster_ids: list[str],
    *,
    n_resamples: int = 500,
    seed: int = 42,
) -> dict[str, float]:
    """Compare candidate vs baseline via paired cluster bootstrap."""
    base_f1 = compute_tsm_f1(y_true, pred_baseline)
    cand_f1 = compute_tsm_f1(y_true, pred_candidate)
    groups: dict[str, list[int]] = {}
    for idx, cid in enumerate(cluster_ids):
        groups.setdefault(cid, []).append(idx)
    keys = sorted(groups.keys())
    rng = np.random.default_rng(seed)
    deltas: list[float] = []
    for _ in range(n_resamples):
        pick = rng.integers(0, len(keys), size=len(keys))
        idxs = [i for k_i in pick for i in groups[keys[int(k_i)]]]
        yt = [y_true[i] for i in idxs]
        yb = [pred_baseline[i] for i in idxs]
        yc = [pred_candidate[i] for i in idxs]
        deltas.append(compute_tsm_f1(yt, yc) - compute_tsm_f1(yt, yb))
    non_pos = sum(1 for d in deltas if d <= 0.0)
    p_val = min(1.0, (2.0 * (non_pos + 1)) / (n_resamples + 1))
    return {
        "delta": round(cand_f1 - base_f1, 4),
        "p_value": round(float(min(1.0, p_val)), 4),
    }
