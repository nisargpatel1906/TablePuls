"""Timezone-aware & overnight-safe menu schedule evaluator (05-menu-management.md)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any
from zoneinfo import ZoneInfo


def _parse_hhmm_minutes(val: str) -> int:
    hh, mm = val.split(":")
    return int(hh) * 60 + int(mm)


def is_menu_scheduled_now(
    schedule_json: dict[str, Any] | None,
    venue_tz: str,
    now_utc: datetime | None = None,
) -> bool:
    """
    Evaluate schedule_json v1 windows against current local time in `venue_tz`.
    Supports same-day windows (e.g. 11:30-15:00) AND overnight windows (e.g. 22:00-02:00).
    NULL/empty windows => always active.
    """
    if not schedule_json:
        return True
    windows = schedule_json.get("windows")
    if not isinstance(windows, list) or len(windows) == 0:
        return True

    base_utc = now_utc or datetime.now(UTC)
    tz: tzinfo
    try:
        tz = ZoneInfo(venue_tz or "UTC")
    except Exception:
        tz = UTC

    local_now = base_utc.astimezone(tz)
    cur_day = local_now.isoweekday()  # 1=Mon..7=Sun
    prev_day = (local_now - timedelta(days=1)).isoweekday()
    cur_mins = local_now.hour * 60 + local_now.minute

    for w in windows:
        if not isinstance(w, dict):
            continue
        days = set(int(d) for d in w.get("days", []) if isinstance(d, int))
        start_s = str(w.get("start", ""))
        end_s = str(w.get("end", ""))
        if not days or ":" not in start_s or ":" not in end_s:
            continue
        start_m = _parse_hhmm_minutes(start_s)
        end_m = _parse_hhmm_minutes(end_s)

        if start_m <= end_m:
            # Standard daytime window
            if cur_day in days and start_m <= cur_mins <= end_m:
                return True
        else:
            # Overnight window crossing midnight (e.g. 22:00 -> 02:00)
            if cur_day in days and cur_mins >= start_m:
                return True
            if prev_day in days and cur_mins <= end_m:
                return True

    return False
