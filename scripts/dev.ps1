# TablePulse Windows PowerShell Task Runner (mirrors Makefile)
param(
    [Parameter(Position = 0)]
    [ValidateSet("check", "test", "e2e", "eval", "license-check", "secret-scan", "smoke", "restore-test")]
    [string]$Task = "check"
)

$ErrorActionPreference = "Stop"

switch ($Task) {
    "license-check" {
        python scripts/license_check.py
    }
    "secret-scan" {
        python scripts/secret_scan.py
    }
    "check" {
        python scripts/license_check.py
        python scripts/secret_scan.py
        if (Test-Path "backend/pyproject.toml") {
            Push-Location backend
            uv run ruff check .
            uv run ruff format --check .
            uv run mypy --strict app
            uv run pytest -q
            Pop-Location
        }
        if (Test-Path "cv-worker/pyproject.toml") {
            Push-Location cv-worker
            uv run ruff check .
            uv run ruff format --check .
            uv run mypy --strict app
            uv run pytest -q
            Pop-Location
        }
        if (Test-Path "ml/pyproject.toml") {
            Push-Location ml
            uv run ruff check .
            uv run ruff format --check .
            uv run pytest -q
            Pop-Location
        }
        if (Test-Path "frontend/package.json") {
            Push-Location frontend
            pnpm lint
            pnpm typecheck
            pnpm test
            Pop-Location
        }
    }
    "test" {
        if (Test-Path "backend/pyproject.toml") { Push-Location backend; uv run pytest -v; Pop-Location }
        if (Test-Path "cv-worker/pyproject.toml") { Push-Location cv-worker; uv run pytest -v; Pop-Location }
        if (Test-Path "ml/pyproject.toml") { Push-Location ml; uv run pytest -v; Pop-Location }
        if (Test-Path "frontend/package.json") { Push-Location frontend; pnpm test; Pop-Location }
    }
    "e2e" {
        Push-Location frontend
        pnpm playwright test
        Pop-Location
    }
    "eval" {
        Push-Location ml
        uv run python evaluate_gate.py --fixture-check
        Pop-Location
    }
    "smoke" {
        python scripts/smoke_test.py
    }
    "restore-test" {
        python scripts/restore_test.py
    }
}
