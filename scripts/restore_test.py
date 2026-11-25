"""Automated PostgreSQL 16 backup & restore verification script (make restore-test)."""

from __future__ import annotations

import subprocess
import sys

DB_CONTAINER = "tablepulse-db-1"
DB_USER = "tablepulse"
SRC_DB = "tablepulse"
VERIFY_DB = "tablepulse_restore_verify"
CORE_TABLES = ["organizations", "venues", "users", "cameras", "tables"]


def _exec_psql(db: str, sql: str) -> str:
    res = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", db, "-At", "-c", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _counts(db: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for tbl in CORE_TABLES:
        out[tbl] = int(_exec_psql(db, f"SELECT COUNT(*) FROM {tbl};"))
    return out


def main() -> int:
    print(f"[1/5] Inspecting source row counts in {SRC_DB}...")
    src_counts = _counts(SRC_DB)
    print("      Source counts:", src_counts)

    print(f"[2/5] Creating custom-format pg_dump inside {DB_CONTAINER}...")
    subprocess.run(
        [
            "docker",
            "exec",
            DB_CONTAINER,
            "pg_dump",
            "-U",
            DB_USER,
            "-Fc",
            "-f",
            "/tmp/tp_verify.dump",
            SRC_DB,
        ],
        check=True,
    )

    try:
        print(f"[3/5] Preparing clean verification DB {VERIFY_DB}...")
        _exec_psql("postgres", f"DROP DATABASE IF EXISTS {VERIFY_DB};")
        _exec_psql("postgres", f"CREATE DATABASE {VERIFY_DB} OWNER {DB_USER};")

        print(f"[4/5] Restoring dump into {VERIFY_DB}...")
        subprocess.run(
            [
                "docker",
                "exec",
                DB_CONTAINER,
                "pg_restore",
                "-U",
                DB_USER,
                "-d",
                VERIFY_DB,
                "--no-owner",
                "/tmp/tp_verify.dump",
            ],
            check=True,
        )

        dst_counts = _counts(VERIFY_DB)
        print("      Restored counts:", dst_counts)
        if src_counts != dst_counts:
            print(f"FAIL: Row count mismatch after restore! src={src_counts}, dst={dst_counts}")
            return 1
        print("[5/5] RESTORE VERIFICATION PASSED (100% row parity across core tables).")
        return 0
    finally:
        _exec_psql("postgres", f"DROP DATABASE IF EXISTS {VERIFY_DB};")
        subprocess.run(["docker", "exec", DB_CONTAINER, "rm", "-f", "/tmp/tp_verify.dump"])


if __name__ == "__main__":
    sys.exit(main())
