.PHONY: dev check test e2e eval smoke bench restore-test license-check

dev:
	docker compose up --build

check: license-check
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict app && uv run pytest -q
	cd cv-worker && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict app && uv run pytest -q
	cd ml && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
	cd frontend && pnpm lint && pnpm typecheck && pnpm test

test:
	cd backend && uv run pytest -v
	cd cv-worker && uv run pytest -v
	cd ml && uv run pytest -v
	cd frontend && pnpm test

e2e:
	cd frontend && pnpm playwright test

eval:
	cd ml && uv run python evaluate_gate.py --fixture-check

smoke:
	docker compose --profile demo up -d --build
	python scripts/smoke_test.py

bench:
	python scripts/run_benchmarks.py

restore-test:
	python scripts/restore_test.py

license-check:
	python scripts/license_check.py
