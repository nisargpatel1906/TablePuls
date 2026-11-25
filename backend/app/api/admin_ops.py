"""Alert Rules, Webhooks, ML Review Queue, System Health, Model Registry, and Privacy Purge (API-019, 020, 022)."""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError, success_response
from app.core.rbac import require_org_role, require_venue_role
from app.core.security import decrypt_field, encrypt_field
from app.core.ssrf import validate_webhook_url
from app.core.valkey_client import (
    get_valkey,
    ping_valkey,
    publish_cv_control,
    set_kill_switch_cache,
)
from app.db.base import get_db, uuid7
from app.db.models import AlertRule, MLModel, MLReviewItem, SystemSetting
from app.schemas.floor_ops import (
    TestWebhookRequest,
    UpdateAlertRuleRequest,
    UpdateMLReviewRequest,
    UpdateSystemSettingsRequest,
)
from app.services.audit import write_audit_log
from app.services.realtime import ws_hub
from app.services.webhooks import dispatch_webhook

router = APIRouter(tags=["admin-ops"])


def _rule_dict(r: AlertRule) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "venue_id": str(r.venue_id),
        "section_name": r.section_name,
        "unattended_service_sec": r.unattended_service_sec,
        "cleaning_alert_delay_sec": r.cleaning_alert_delay_sec,
        "occupancy_debounce_sec": r.occupancy_debounce_sec,
        "departure_debounce_sec": r.departure_debounce_sec,
        "min_confidence": r.min_confidence,
        "require_bussing_confirmation": r.require_bussing_confirmation,
        "has_webhook_url": r.webhook_url_encrypted is not None,
        "quiet_hours_enabled": r.quiet_hours_enabled,
    }


@router.get("/api/v1/venues/{venue_id}/alert-rules")
async def get_alert_rules(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="alert_rules.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-019 (get): Return venue/section alert threshold rules."""
    rules = (
        (
            await db.execute(
                select(AlertRule).where(
                    AlertRule.venue_id == venue_id,
                    AlertRule.organization_id == actor.organization_id,
                    AlertRule.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rules:
        default_rule = AlertRule(
            id=uuid7(), organization_id=actor.organization_id, venue_id=venue_id
        )
        db.add(default_rule)
        await db.commit()
        rules = [default_rule]
    return success_response({"items": [_rule_dict(r) for r in rules]})


@router.patch("/api/v1/venues/{venue_id}/alert-rules")
async def update_alert_rules(
    venue_id: uuid.UUID,
    body: UpdateAlertRuleRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="alert_rules.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-019 (update): Update alert thresholds and SSRF-validated webhook URL/secret."""
    q = select(AlertRule).where(
        AlertRule.venue_id == venue_id,
        AlertRule.organization_id == actor.organization_id,
        AlertRule.deleted_at.is_(None),
    )
    if body.section_name is None:
        q = q.where(AlertRule.section_name.is_(None))
    else:
        q = q.where(AlertRule.section_name == body.section_name.strip())

    rule = (await db.execute(q)).scalar_one_or_none()
    if rule is None:
        rule = AlertRule(
            id=uuid7(),
            organization_id=actor.organization_id,
            venue_id=venue_id,
            section_name=body.section_name.strip() if body.section_name else None,
        )
        db.add(rule)

    if body.unattended_service_sec is not None:
        rule.unattended_service_sec = body.unattended_service_sec
    if body.cleaning_alert_delay_sec is not None:
        rule.cleaning_alert_delay_sec = body.cleaning_alert_delay_sec
    if body.occupancy_debounce_sec is not None:
        rule.occupancy_debounce_sec = body.occupancy_debounce_sec
    if body.departure_debounce_sec is not None:
        rule.departure_debounce_sec = body.departure_debounce_sec
    if body.min_confidence is not None:
        rule.min_confidence = body.min_confidence
    if body.require_bussing_confirmation is not None:
        rule.require_bussing_confirmation = body.require_bussing_confirmation
    if body.quiet_hours_enabled is not None:
        rule.quiet_hours_enabled = body.quiet_hours_enabled
    if body.webhook_url is not None:
        validated = validate_webhook_url(body.webhook_url)
        rule.webhook_url_encrypted = encrypt_field(validated)
    if body.webhook_secret is not None:
        rule.webhook_secret_encrypted = encrypt_field(body.webhook_secret)

    await db.flush()
    payload = _rule_dict(rule)
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="UPDATE_ALERT_RULES",
        target_type="alert_rule",
        target_id=rule.id,
        after_json=payload,
        request=request,
    )
    await db.commit()
    await publish_cv_control({"event": "rules_updated", "venue_id": str(venue_id)})
    return success_response(payload)


@router.post("/api/v1/venues/{venue_id}/alert-rules/test-webhook")
async def test_webhook(
    venue_id: uuid.UUID,
    body: TestWebhookRequest,
    actor: Annotated[Any, Depends(require_venue_role(capability="alert_rules.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-019 (test): Validate SSRF safety and send HMAC-SHA256 test webhook."""
    url = body.webhook_url
    secret = body.webhook_secret or ""
    if not url:
        rule = (
            await db.execute(
                select(AlertRule).where(
                    AlertRule.venue_id == venue_id,
                    AlertRule.section_name.is_(None),
                    AlertRule.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if rule is None or not rule.webhook_url_encrypted:
            raise AppError(400, "VALIDATION_ERROR", "No webhook URL configured")
        url = decrypt_field(rule.webhook_url_encrypted)
        if rule.webhook_secret_encrypted and not secret:
            secret = decrypt_field(rule.webhook_secret_encrypted)

    ok, status_code, detail = await dispatch_webhook(
        url=url,
        secret=secret,
        payload={
            "event": "tablepulse.test",
            "venue_id": str(venue_id),
            "ts": datetime.now(UTC).isoformat(),
        },
        max_attempts=1,
        bypass_kill_switch=True,
    )
    if not ok:
        raise AppError(422, "CAMERA_UNREACHABLE", f"Test webhook failed: {detail}")
    return success_response({"delivered": True, "http_status": status_code, "detail": detail})


@router.get("/api/v1/venues/{venue_id}/ml-review")
async def list_ml_review_items(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="ml_review.label"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    review_status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> JSONResponse:
    """API-020 (list): Paginated ML confidence & human-review queue."""
    q = select(MLReviewItem).where(
        MLReviewItem.venue_id == venue_id,
        MLReviewItem.organization_id == actor.organization_id,
    )
    if review_status:
        q = q.where(MLReviewItem.review_status == review_status)
    rows = (await db.execute(q.order_by(MLReviewItem.created_at.desc()))).scalars().all()
    total = len(rows)
    start = (page - 1) * page_size
    reviewed_rows = [r for r in rows if r.review_status == "REVIEWED"]
    agreed = sum(1 for r in reviewed_rows if r.human_state == r.predicted_state)
    agreement_rate = round(agreed / len(reviewed_rows), 3) if reviewed_rows else None

    items = [
        {
            "id": str(r.id),
            "table_id": str(r.table_id),
            "camera_id": str(r.camera_id),
            "has_snapshot": bool(r.snapshot_path and Path(r.snapshot_path).exists()),
            "predicted_state": r.predicted_state,
            "predicted_guest_count": r.predicted_guest_count,
            "confidence": r.confidence,
            "trigger_reason": r.trigger_reason,
            "review_status": r.review_status,
            "human_state": r.human_state,
            "human_guest_count": r.human_guest_count,
            "issue_tags": r.issue_tags or [],
            "created_at": r.created_at.isoformat(),
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in rows[start : start + page_size]
    ]
    return success_response(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "agreement_rate": agreement_rate,
        }
    )


@router.patch("/api/v1/venues/{venue_id}/ml-review/{item_id}")
async def submit_ml_review(
    venue_id: uuid.UUID,
    item_id: uuid.UUID,
    body: UpdateMLReviewRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_venue_role(capability="ml_review.label"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-020 (label): Submit human ground-truth state, guest count, and tags."""
    item = (
        await db.execute(
            select(MLReviewItem).where(
                MLReviewItem.id == item_id,
                MLReviewItem.venue_id == venue_id,
                MLReviewItem.organization_id == actor.organization_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "ML review item not found")

    item.review_status = body.review_status
    item.human_state = body.human_state
    item.human_guest_count = body.human_guest_count
    item.issue_tags = body.issue_tags
    item.reviewed_by = actor.id
    item.reviewed_at = datetime.now(UTC)

    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        venue_id=venue_id,
        actor_user_id=actor.id,
        action="SUBMIT_ML_REVIEW",
        target_type="ml_review_item",
        target_id=item.id,
        after_json={"review_status": item.review_status, "human_state": item.human_state},
        request=request,
    )
    await db.commit()
    return success_response({"id": str(item.id), "review_status": item.review_status})


@router.get("/api/v1/venues/{venue_id}/ml-review/export")
async def export_ml_review_bundle(
    venue_id: uuid.UUID,
    actor: Annotated[Any, Depends(require_venue_role(capability="ml_review.export"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """API-020 (export): OWNER-only anonymized zip export (face-blurred crops + JSON annotations)."""
    items = (
        (
            await db.execute(
                select(MLReviewItem).where(
                    MLReviewItem.venue_id == venue_id,
                    MLReviewItem.organization_id == actor.organization_id,
                    MLReviewItem.review_status == "REVIEWED",
                )
            )
        )
        .scalars()
        .all()
    )

    buf = io.BytesIO()
    annotations: list[dict[str, Any]] = []
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            crop_name: str | None = None
            if item.snapshot_path and Path(item.snapshot_path).exists():
                crop_name = f"crops/{item.id}.jpg"
                zf.write(item.snapshot_path, arcname=crop_name)
            annotations.append(
                {
                    "id": str(item.id),
                    "table_id": str(item.table_id),
                    "predicted_state": item.predicted_state,
                    "predicted_guest_count": item.predicted_guest_count,
                    "human_state": item.human_state,
                    "human_guest_count": item.human_guest_count,
                    "issue_tags": item.issue_tags or [],
                    "crop_file": crop_name,
                }
            )
        zf.writestr(
            "annotations.json",
            json.dumps({"venue_id": str(venue_id), "items": annotations}, indent=2),
        )

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="tablepulse-review-{venue_id}.zip"'},
    )


@router.get("/api/v1/org/system")
async def get_system_overview(
    actor: Annotated[Any, Depends(require_org_role(capability="system.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-022 (get): OWNER-only system health, kill switch, retention policy, and model registry."""
    sys_set = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.organization_id == actor.organization_id)
        )
    ).scalar_one_or_none()
    if sys_set is None:
        sys_set = SystemSetting(organization_id=actor.organization_id)
        db.add(sys_set)
        await db.commit()

    models = (await db.execute(select(MLModel).order_by(MLModel.created_at.desc()))).scalars().all()
    if not models:
        # Honest zero-shot experimental baseline when no custom trained model exists yet
        baseline = MLModel(
            id=uuid7(),
            model_role="DETECTOR",
            version="tablepulse-detector-b1@0.1.0",
            artifact_uri="builtin://rfdetr-nano-zero-shot",
            artifact_sha256="0" * 64,
            dataset_version="NONE",
            eval_metrics_json={"TSM-F1": "NOT YET MEASURED"},
            gate_status="NOT_MEASURED",
            channel="experimental",
            is_active=True,
        )
        db.add(baseline)
        await db.commit()
        models = [baseline]

    valkey_ok = await ping_valkey()
    cv_heartbeat: str | None = None
    try:
        cv_heartbeat = await get_valkey().get("tp:cv:heartbeat")
    except Exception:
        cv_heartbeat = None

    return success_response(
        {
            "health": {
                "api": "ok",
                "postgres": "ok",
                "valkey": "ok" if valkey_ok else "down",
                "cv_worker": "ok" if cv_heartbeat else "offline",
            },
            "settings": {
                "ai_inference_enabled": sys_set.ai_inference_enabled,
                "face_blur_enforced": sys_set.face_blur_enforced,
                "snapshot_retention_days": sys_set.snapshot_retention_days,
                "analytics_retention_days": sys_set.analytics_retention_days,
            },
            "models": [
                {
                    "id": str(m.id),
                    "model_role": m.model_role,
                    "version": m.version,
                    "artifact_uri": m.artifact_uri,
                    "dataset_version": m.dataset_version,
                    "eval_metrics_json": m.eval_metrics_json,
                    "gate_status": m.gate_status,
                    "channel": m.channel,
                    "is_active": m.is_active,
                    "created_at": m.created_at.isoformat(),
                }
                for m in models
            ],
        }
    )


@router.patch("/api/v1/org/system")
async def update_system_settings(
    body: UpdateSystemSettingsRequest,
    request: Request,
    actor: Annotated[Any, Depends(require_org_role(capability="system.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-022 (patch): Toggle global AI kill switch, face blur, and retention policies."""
    sys_set = (
        await db.execute(
            select(SystemSetting).where(SystemSetting.organization_id == actor.organization_id)
        )
    ).scalar_one_or_none()
    if sys_set is None:
        sys_set = SystemSetting(organization_id=actor.organization_id)
        db.add(sys_set)

    before = {
        "ai_inference_enabled": sys_set.ai_inference_enabled,
        "face_blur_enforced": sys_set.face_blur_enforced,
        "snapshot_retention_days": sys_set.snapshot_retention_days,
        "analytics_retention_days": sys_set.analytics_retention_days,
    }
    if body.ai_inference_enabled is not None:
        sys_set.ai_inference_enabled = body.ai_inference_enabled
    if body.face_blur_enforced is not None:
        sys_set.face_blur_enforced = body.face_blur_enforced
    if body.snapshot_retention_days is not None:
        sys_set.snapshot_retention_days = body.snapshot_retention_days
    if body.analytics_retention_days is not None:
        sys_set.analytics_retention_days = body.analytics_retention_days
    sys_set.updated_by = actor.id
    sys_set.updated_at = datetime.now(UTC)

    after = {
        "ai_inference_enabled": sys_set.ai_inference_enabled,
        "face_blur_enforced": sys_set.face_blur_enforced,
        "snapshot_retention_days": sys_set.snapshot_retention_days,
        "analytics_retention_days": sys_set.analytics_retention_days,
    }
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="TOGGLE_KILL_SWITCH"
        if before["ai_inference_enabled"] != after["ai_inference_enabled"]
        else "UPDATE_SYSTEM_SETTINGS",
        target_type="system_settings",
        target_id=actor.organization_id,
        before_json=before,
        after_json=after,
        request=request,
    )
    await db.commit()

    await set_kill_switch_cache(str(actor.organization_id), sys_set.ai_inference_enabled)
    await ws_hub.broadcast_all(
        {
            "type": "system.kill_switch_changed",
            "data": {"ai_inference_enabled": sys_set.ai_inference_enabled},
        }
    )
    return success_response(after)


@router.post("/api/v1/org/system/models/{model_id}/activate")
async def activate_model(
    model_id: uuid.UUID,
    request: Request,
    actor: Annotated[Any, Depends(require_org_role(capability="system.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-022 (activate model): Switch active model version (stable requires gate_status == PASS)."""
    model = (await db.execute(select(MLModel).where(MLModel.id == model_id))).scalar_one_or_none()
    if model is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Model version not found")
    if model.channel == "stable" and model.gate_status != "PASS":
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Cannot activate stable model without a passing ML evaluation gate (gate_status=PASS)",
        )

    await db.execute(
        update(MLModel).where(MLModel.model_role == model.model_role).values(is_active=False)
    )
    model.is_active = True
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="ACTIVATE_MODEL",
        target_type="ml_model",
        target_id=model.id,
        after_json={
            "version": model.version,
            "channel": model.channel,
            "gate_status": model.gate_status,
        },
        request=request,
    )
    await db.commit()
    await publish_cv_control({"event": "model_reload", "model_version": model.version})
    return success_response({"activated": True, "version": model.version})


@router.post("/api/v1/org/system/purge-snapshots")
async def purge_snapshots_now(
    request: Request,
    actor: Annotated[Any, Depends(require_org_role(capability="privacy.purge"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """API-022 (purge): Immediately delete all stored review crop files and audit log."""
    snap_dir = Path(get_settings().snapshot_storage_dir)
    deleted_files = 0
    if snap_dir.exists():
        for f in snap_dir.rglob("*.jpg"):
            f.unlink(missing_ok=True)
            deleted_files += 1

    await db.execute(
        update(MLReviewItem)
        .where(MLReviewItem.organization_id == actor.organization_id)
        .values(snapshot_path=None)
    )
    await write_audit_log(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="PURGE_SNAPSHOTS",
        target_type="system_settings",
        target_id=actor.organization_id,
        after_json={"deleted_files": deleted_files},
        request=request,
    )
    await db.commit()
    return success_response({"purged_files": deleted_files})


async def purge_expired_snapshots_once(db: AsyncSession) -> int:
    """Retention helper: delete snapshot files older than org snapshot_retention_days."""
    settings_rows = (await db.execute(select(SystemSetting))).scalars().all()
    purged = 0
    now = datetime.now(UTC)
    for st in settings_rows:
        cutoff = now - timedelta(days=int(st.snapshot_retention_days))
        items = (
            (
                await db.execute(
                    select(MLReviewItem).where(
                        MLReviewItem.organization_id == st.organization_id,
                        MLReviewItem.snapshot_path.is_not(None),
                        MLReviewItem.created_at < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        for item in items:
            if item.snapshot_path:
                Path(item.snapshot_path).unlink(missing_ok=True)
                item.snapshot_path = None
                purged += 1
    await db.commit()
    return purged
