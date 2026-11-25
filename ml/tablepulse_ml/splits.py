"""Leakage-free dataset split generator & 5-invariant verifier (docs/07 §6)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from tablepulse_ml.schema import EvalClip


@dataclass(frozen=True)
class DatasetSplits:
    train: list[EvalClip]
    val: list[EvalClip]
    test: list[EvalClip]


def generate_leakage_free_splits(
    clips: list[EvalClip],
    *,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    min_temporal_gap_sec: int = 300,
) -> DatasetSplits:
    """Partition clips by (venue_id, session_id) with temporal ordering to prevent frame leakage."""
    if train_ratio <= 0 or val_ratio <= 0 or train_ratio + val_ratio >= 1.0:
        raise ValueError("Invalid split ratios")

    # Group strictly by session_id (sessions stay atomic across splits)
    sessions: dict[str, list[EvalClip]] = {}
    for clip in clips:
        sessions.setdefault(clip.session_id, []).append(clip)

    ordered_sessions = sorted(
        sessions.values(),
        key=lambda grp: (min(c.timestamp_epoch for c in grp), grp[0].session_id),
    )

    n = len(ordered_sessions)
    if n < 3:
        raise ValueError("At least 3 distinct sessions are required to form train/val/test splits")

    n_train = max(1, int(round(n * train_ratio)))
    n_val = max(1, int(round(n * val_ratio)))
    if n_train + n_val >= n:
        n_train = max(1, n - 2)
        n_val = 1

    train_grps = ordered_sessions[:n_train]
    val_grps = ordered_sessions[n_train : n_train + n_val]
    test_grps = ordered_sessions[n_train + n_val :]

    train = [c for g in train_grps for c in g]
    val = [c for g in val_grps for c in g]
    test = [c for g in test_grps for c in g]

    assert_zero_leakage(
        DatasetSplits(train=train, val=val, test=test),
        min_temporal_gap_sec=min_temporal_gap_sec,
        require_venue_disjoint=False,
    )
    return DatasetSplits(train=train, val=val, test=test)


def assert_zero_leakage(
    splits: DatasetSplits,
    *,
    min_temporal_gap_sec: int = 0,
    require_venue_disjoint: bool = False,
) -> None:
    """Assert 5 strict zero-leakage invariants across train, val, and test splits."""
    buckets = {"train": splits.train, "val": splits.val, "test": splits.test}

    for a_name, b_name in [("train", "val"), ("train", "test"), ("val", "test")]:
        a_clips = buckets[a_name]
        b_clips = buckets[b_name]

        # 1. No clip_id overlap
        if {c.clip_id for c in a_clips} & {c.clip_id for c in b_clips}:
            raise ValueError(f"Clip ID leakage between {a_name} and {b_name}")

        # 2. No session_id overlap
        if {c.session_id for c in a_clips} & {c.session_id for c in b_clips}:
            raise ValueError(f"Session ID leakage between {a_name} and {b_name}")

        # 3. No exact frame_hash duplicate overlap
        if {c.frame_hash for c in a_clips} & {c.frame_hash for c in b_clips}:
            raise ValueError(f"Frame hash leakage between {a_name} and {b_name}")

        # 4. Optional strict venue disjointness
        if require_venue_disjoint and (
            {c.venue_id for c in a_clips} & {c.venue_id for c in b_clips}
        ):
            raise ValueError(f"Venue ID leakage between {a_name} and {b_name}")

        # 5. Same-camera temporal gap invariant
        if min_temporal_gap_sec > 0:
            by_cam_a: dict[str, list[int]] = {}
            for c in a_clips:
                by_cam_a.setdefault(c.camera_id, []).append(c.timestamp_epoch)
            for c in b_clips:
                for ts_a in by_cam_a.get(c.camera_id, []):
                    if abs(c.timestamp_epoch - ts_a) < min_temporal_gap_sec:
                        raise ValueError(
                            f"Temporal gap violation on cam {c.camera_id} ({a_name}/{b_name})"
                        )


def deterministic_split_digest(splits: DatasetSplits) -> str:
    h = hashlib.sha256()
    for name, grp in [("train", splits.train), ("val", splits.val), ("test", splits.test)]:
        h.update(name.encode())
        for c in sorted(grp, key=lambda x: x.clip_id):
            h.update(c.clip_id.encode())
    return h.hexdigest()[:16]
