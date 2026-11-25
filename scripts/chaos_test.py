"""Chaos & Degraded-Mode verification suite (all 4 required scenarios)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core import valkey_client  # noqa: E402
from app.services import webhooks  # noqa: E402

_sm_spec = importlib.util.spec_from_file_location(
    "cv_state_machine", ROOT / "cv-worker" / "app" / "state_machine.py"
)
assert _sm_spec and _sm_spec.loader
_sm_mod = importlib.util.module_from_spec(_sm_spec)
sys.modules["cv_state_machine"] = _sm_mod
_sm_spec.loader.exec_module(_sm_mod)
TableStateMachine = _sm_mod.TableStateMachine
TableTrackerState = _sm_mod.TableTrackerState
TableObservation = _sm_mod.TableObservation
TableState = _sm_mod.TableState


def test_camera_drop_transitions_to_unknown() -> None:
    """Scenario 1: RTSP/camera stream drop -> table transitions safely to UNKNOWN (never FREE)."""
    sm = TableStateMachine()
    tracker = TableTrackerState(table_id="chaos-t1")
    sm.step(
        tracker,
        TableObservation(
            timestamp_s=100.0,
            seated_guest_count=0,
            staff_at_perimeter=False,
            cleanliness_label="CLEAN",
            cleanliness_conf=0.9,
            detection_conf=0.95,
            camera_online=True,
        ),
    )
    assert tracker.state == TableState.FREE

    ev = sm.step(
        tracker,
        TableObservation(
            timestamp_s=135.0,
            seated_guest_count=0,
            staff_at_perimeter=False,
            cleanliness_label="UNKNOWN",
            cleanliness_conf=0.0,
            detection_conf=0.0,
            camera_online=False,
        ),
    )
    assert ev is not None
    assert tracker.state == TableState.UNKNOWN, f"Expected UNKNOWN, got {tracker.state}"
    print("  [PASS] Chaos 1: Camera/RTSP drop safely sets table state to UNKNOWN (never FREE)")


async def test_valkey_down_fail_closed() -> None:
    """Scenario 2 & 3: Valkey unreachable -> rate limits fail closed & kill switch defaults False."""
    orig_client = valkey_client._client
    valkey_client._local_rate_limits.clear()

    class BrokenValkey:
        async def incr(self, _k: str):
            raise ConnectionError("Simulated Valkey outage")

        async def get(self, _k: str):
            raise ConnectionError("Simulated Valkey outage")

        async def ping(self):
            raise ConnectionError("Simulated Valkey outage")

    try:
        valkey_client._client = BrokenValkey()  # type: ignore[assignment]
        assert (await valkey_client.ping_valkey()) is False
        results = [
            (await valkey_client.check_rate_limit("chaos:ip", 3, 60, fail_closed=True))[0]
            for _ in range(4)
        ]
        assert results == [True, True, True, False], f"Unexpected fallback sequence: {results}"
        from app.config import Settings

        default_cfg = Settings(_env_file=None)
        assert default_cfg.ai_inference_enabled is False, "Missing kill switch must default False"
        assert default_cfg.webhooks_enabled is False, "Missing webhooks flag must default False"
    finally:
        valkey_client._client = orig_client
    print("  [PASS] Chaos 2 & 3: Valkey outage fails closed & missing kill switches default False")


async def test_webhook_failure_circuit_breaker() -> None:
    """Scenario 4: Repeated HTTP 500 responses trigger retry bounding & circuit breaker."""
    import httpx

    webhooks.reset_webhook_circuits()
    failing_transport = httpx.MockTransport(lambda _req: httpx.Response(500, text="server error"))
    # Trigger failures up to breaker threshold (10 consecutive failures)
    for _ in range(10):
        ok, code, _detail = await webhooks.dispatch_webhook(
            url="https://93.184.216.34/webhook",
            secret="test-secret-123456",
            payload={"event": "chaos.test"},
            max_attempts=1,
            transport=failing_transport,
            bypass_kill_switch=True,
        )
        assert ok is False and code == 500

    # Subsequent call while circuit is open short-circuits before hitting transport
    ok_open, code_open, detail_open = await webhooks.dispatch_webhook(
        url="https://93.184.216.34/webhook",
        secret="test-secret-123456",
        payload={"event": "chaos.test"},
        max_attempts=1,
        transport=failing_transport,
        bypass_kill_switch=True,
    )
    assert ok_open is False and code_open is None
    assert "circuit" in detail_open.lower() or "open" in detail_open.lower()
    print(f"  [PASS] Chaos 4: Webhook 500 retries + circuit breaker open verified ({detail_open})")


def main() -> int:
    print("Running TablePulse Chaos & Degraded-Mode Suite...")
    test_camera_drop_transitions_to_unknown()
    asyncio.run(test_valkey_down_fail_closed())
    asyncio.run(test_webhook_failure_circuit_breaker())
    print("CHAOS SUITE PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
