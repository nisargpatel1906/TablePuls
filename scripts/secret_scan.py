#!/usr/bin/env python3
"""
Local Secret & Credential Hygiene Scanner (complementing gitleaks in CI).
Fails if .env is tracked in git or if high-risk secret patterns appear outside test/example files.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private Key Block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("RTSP Embedded Password", re.compile(r"rtsp://[^/\s:@]+:[^/\s@]+@(?!example\.com|192\.168\.1\.40)")),
]

ALLOWLIST_PREFIXES = (
    ".env.example",
    "deploy/env.example",
    "AGENTS.md",
    "docs/",
    ".gitleaks.toml",
    "scripts/secret_scan.py",
)


def main() -> int:
    errors: list[str] = []

    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    for rel in tracked:
        if rel == ".env" or (rel.startswith(".env.") and rel != ".env.example"):
            errors.append(f"Tracked secret env file found in git: {rel}")
        if any(rel.startswith(p) for p in ALLOWLIST_PREFIXES) or "/tests/" in f"/{rel}":
            continue
        p = ROOT / rel
        if not p.is_file() or p.suffix in {".png", ".jpg", ".jpeg", ".mp4", ".onnx", ".ico", ".woff2"}:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for label, pat in SECRET_PATTERNS:
            if pat.search(text):
                errors.append(f"Potential {label} detected in tracked file: {rel}")

    if errors:
        print("SECRET SCAN FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("SECRET SCAN PASSED: zero tracked .env or exposed credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
