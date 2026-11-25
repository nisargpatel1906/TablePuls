# Staff & Customer Privacy Notices (Operator Templates)

## 1. Staff Privacy Notice Template

- **Scope & Purpose:** **[VENUE NAME]** operates TablePulse solely for operational table readiness (identifying unoccupied, occupied, bussing-needed, and unattended service states).
- **Non-Monitoring Commitment:** TablePulse enforces **no per-employee scoring, productivity tracking, individual staff identification, or audio surveillance**.
- **Access Controls:** Access to floor views, review crops, and camera feeds is restricted strictly by role (`packages/rbac/matrix.yaml`) and logged in an immutable audit trail.

## 2. Customer Privacy Notice Template

- **Data Collected:** Anonymous aggregate occupancy counts (`integer`), table transition timestamps, and wait times.
- **Phone Numbers (Waitlist Optional):** If provided for SMS/host callback, phone numbers are encrypted using AES-256-GCM at rest (`waitlist_entries.phone_encrypted`) and never displayed in analytics or exports.
- **Retention:** Temporary face-blurred ML review crops expire automatically after `snapshot_retention_days` (default: 7 days) or via immediate OWNER purge (`POST /api/v1/org/system/purge-snapshots`).
