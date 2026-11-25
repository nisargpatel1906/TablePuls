#!/usr/bin/env python3
"""
TablePulse Automated License, Prohibited-Package & Privacy-Library Gate.
Checks pyproject.toml, package.json, optional pip-licenses/license-checker JSON,
and scans source trees for banned packages, restricted RF-DETR sizes, and biometric libs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # Fallback minimal parser if PyYAML is not installed yet


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWLIST = ROOT / "config" / "license-allowlist.yaml"


def _load_allowlist(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        return {k: list(v or []) for k, v in data.items()}
    # Minimal YAML list parser fallback (no external deps needed for Stage 0 bootstrap)
    result: dict[str, list[str]] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_key = line[:-1].strip()
            result[current_key] = []
        elif line.strip().startswith("- ") and current_key is not None:
            val = line.strip()[2:].strip().strip('"').strip("'")
            result[current_key].append(val)
    return result


def _normalize_pkg_name(spec: str) -> str:
    return re.split(r"[<>=!~;\[\s]", spec.strip(), maxsplit=1)[0].lower().replace("_", "-")


def check_manifests(root: Path, allowlist: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    banned = {p.lower().replace("_", "-") for p in allowlist.get("banned_packages", [])}

    for pyproject in root.rglob("pyproject.toml"):
        if ".venv" in pyproject.parts or "node_modules" in pyproject.parts:
            continue
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        deps: list[str] = list(data.get("project", {}).get("dependencies", []))
        opt_deps = data.get("project", {}).get("optional-dependencies", {})
        for group in opt_deps.values():
            deps.extend(group)
        for dep in deps:
            name = _normalize_pkg_name(dep)
            if name in banned:
                errors.append(f"Banned Python dependency '{name}' found in {pyproject.relative_to(root)}")
        # Check uv.lock or requirements if present nearby
    for req_file in list(root.rglob("requirements*.txt")) + list(root.rglob("uv.lock")):
        if ".venv" in req_file.parts or "node_modules" in req_file.parts:
            continue
        content = req_file.read_text(encoding="utf-8", errors="ignore").lower()
        for pkg in banned:
            if re.search(rf'(^|["\s=]){re.escape(pkg)}(["\s=<>!~\[]|$)', content, re.MULTILINE):
                errors.append(f"Banned package '{pkg}' referenced in {req_file.relative_to(root)}")

    for pkg_json in root.rglob("package.json"):
        if "node_modules" in pkg_json.parts or ".next" in pkg_json.parts:
            continue
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            for name in data.get(section, {}):
                if name.lower() in banned:
                    errors.append(f"Banned JS dependency '{name}' found in {pkg_json.relative_to(root)}")

    return errors


def check_source_prohibitions(root: Path, allowlist: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    banned_variants = allowlist.get("banned_rfdetr_variants", [])
    banned_pkgs = allowlist.get("banned_packages", [])
    scan_dirs = [d for d in ("backend", "cv-worker", "ml", "frontend", "packages") if (root / d).exists()]
    for d in scan_dirs:
        for file_path in (root / d).rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in {"node_modules", ".venv", "__pycache__", ".next", "dist"} for part in file_path.parts):
                continue
            if file_path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml", ".json", ".toml"}:
                continue
            # Skip test files that intentionally assert banned-input rejection
            rel = file_path.relative_to(root).as_posix()
            if "/tests/" in f"/{rel}" or rel.endswith(".test.ts") or rel.endswith(".test.tsx"):
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for variant in banned_variants:
                if variant in text:
                    errors.append(f"Restricted RF-DETR variant '{variant}' (Roboflow PML 1.0) in {rel}")
            for pkg in banned_pkgs:
                if re.search(rf"\b(import|from)\s+{re.escape(pkg.replace('-', '_'))}\b", text):
                    errors.append(f"Prohibited import '{pkg}' in {rel}")
    return errors


def check_pip_licenses_json(report_path: Path, allowlist: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    data = json.loads(report_path.read_text(encoding="utf-8"))
    allowed = [s.lower() for s in allowlist.get("allowed_spdx_substrings", [])]
    banned = [s.lower() for s in allowlist.get("banned_license_substrings", [])]
    banned_pkgs = {p.lower().replace("_", "-") for p in allowlist.get("banned_packages", [])}

    for item in data:
        name = str(item.get("Name", "")).lower().replace("_", "-")
        lic = str(item.get("License", ""))
        lic_l = lic.lower()
        if name in banned_pkgs:
            errors.append(f"Banned package in pip-licenses output: {name}")
        # Check explicit GPL/AGPL bans carefully (avoid matching LGPL when checking GPL)
        for b in banned:
            if b.startswith("gpl") and "lgpl" in lic_l:
                continue
            if b in lic_l and not ("lgpl" in lic_l and b == "gpl"):
                errors.append(f"Banned license '{lic}' on Python package '{item.get('Name')}' (matched '{b}')")
                break
        else:
            if lic_l not in {"unknown", ""} and not any(a in lic_l for a in allowed):
                errors.append(f"Unapproved license '{lic}' on Python package '{item.get('Name')}'")
    return errors


def check_npm_licenses_json(report_path: Path, allowlist: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    data = json.loads(report_path.read_text(encoding="utf-8"))
    allowed = [s.lower() for s in allowlist.get("allowed_spdx_substrings", [])]
    banned = [s.lower() for s in allowlist.get("banned_license_substrings", [])]

    for pkg_id, meta in data.items():
        lic = str(meta.get("licenses", ""))
        lic_l = lic.lower()
        for b in banned:
            if b in lic_l and not ("lgpl" in lic_l and "gpl" in b):
                errors.append(f"Banned license '{lic}' on npm package '{pkg_id}'")
                break
        else:
            if lic_l and not any(a in lic_l for a in allowed):
                errors.append(f"Unapproved license '{lic}' on npm package '{pkg_id}'")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="TablePulse License & Privacy Hygiene Checker")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--pip-licenses-json", type=Path, default=None)
    parser.add_argument("--npm-licenses-json", type=Path, default=None)
    args = parser.parse_args()

    allowlist = _load_allowlist(args.allowlist)
    errors: list[str] = []
    errors.extend(check_manifests(args.root, allowlist))
    errors.extend(check_source_prohibitions(args.root, allowlist))

    if args.pip_licenses_json and args.pip_licenses_json.exists():
        errors.extend(check_pip_licenses_json(args.pip_licenses_json, allowlist))
    if args.npm_licenses_json and args.npm_licenses_json.exists():
        errors.extend(check_npm_licenses_json(args.npm_licenses_json, allowlist))

    if errors:
        print("LICENSE CHECK FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("LICENSE CHECK PASSED: zero prohibited packages or licenses found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
