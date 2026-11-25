"""API + Frontend Smoke Test verifying live runtime health & envelope contract."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
import json


def get_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]


def main() -> int:
    api = os.getenv("TABLEPULSE_SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    web = os.getenv("TABLEPULSE_SMOKE_WEB_URL", "http://127.0.0.1:3000").rstrip("/")

    health = get_json(f"{api}/api/v1/health")
    if health.get("success") is not True:
        print("FAIL: API health envelope unexpected:", health)
        return 1

    bs = get_json(f"{api}/api/v1/auth/bootstrap-status")
    if bs.get("success") is not True:
        print("FAIL: bootstrap-status envelope unexpected:", bs)
        return 1

    for route in ["/login", "/register", "/reset-password", "/onboarding"]:
        try:
            with urllib.request.urlopen(f"{web}{route}", timeout=8) as resp:
                if resp.status >= 400:
                    print(f"FAIL: {route} returned HTTP {resp.status}")
                    return 1
        except urllib.error.URLError as exc:
            print(f"FAIL: Web route {route} unreachable: {exc}")
            return 1

    print(f"SMOKE TEST PASSED (api={api}, web={web}, demo_mode={bs['data']})")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    sys.exit(main())
