from __future__ import annotations

from datetime import UTC, datetime, timedelta


def login(client, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_rule_management_supports_preset_and_custom_rules(client) -> None:
    token = login(client, "admin", "admin123")

    list_response = client.get("/api/v1/rules", headers=auth_headers(token))
    assert list_response.status_code == 200
    rules = list_response.json()["data"]
    assert {rule["rule_type"] for rule in rules} >= {"lying_duration", "zone_dwell", "no_drinking"}

    create_response = client.post(
        "/api/v1/rules",
        json={
            "name": "测试自定义区域规则",
            "description": "测试阶段四自定义规则",
            "rule_type": "zone_dwell",
            "severity": "high",
            "threshold_minutes": 15,
            "device_id": 1,
            "zone_name": "Water Zone",
            "behavior_type": None,
            "is_enabled": True,
            "config": {"from_test": True},
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    created_rule = create_response.json()["data"]
    assert created_rule["source"] == "custom"

    status_response = client.patch(
        f"/api/v1/rules/{created_rule['id']}/status",
        json={"is_enabled": False},
        headers=auth_headers(token),
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["is_enabled"] is False

    delete_response = client.delete(
        f"/api/v1/rules/{created_rule['id']}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 200


def test_import_event_generates_alerts_and_allows_status_update(client, monkeypatch) -> None:
    def fake_inference_service(payload: dict[str, object], **_kwargs) -> dict[str, object]:
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        return {
            "request_id": payload["request_id"],
            "service": "cow-monitor-inference",
            "model_name": "stage4-demo-model",
            "model_version": "0.4.0",
            "inference_source": "demo-pipeline",
            "processed_at": datetime.now(UTC).isoformat(),
            "behavior_events": [
                {
                    "device_code": payload["device_code"],
                    "event_time": occurred_at.isoformat(),
                    "behavior_type": "lying",
                    "cow_count": 2,
                    "confidence": 0.95,
                    "zone_name": "Water Zone",
                    "notes": "阶段四告警测试",
                }
            ],
            "raw_metadata": {"pipeline_mode": "demo"},
        }

    monkeypatch.setattr(
        "app.modules.events.router.invoke_inference_service",
        fake_inference_service,
    )

    token = login(client, "admin", "admin123")
    occurred_at = datetime.now(UTC) - timedelta(minutes=40)

    import_response = client.post(
        "/api/v1/events/import",
        json={
            "device_code": "CAM-TEST-001",
            "source_type": "video",
            "source_uri": "demo://tests/stage4-alert.mp4",
            "occurred_at": occurred_at.isoformat(),
            "metadata": {},
        },
        headers=auth_headers(token),
    )
    assert import_response.status_code == 200

    list_response = client.get("/api/v1/alerts", headers=auth_headers(token))
    assert list_response.status_code == 200
    payload = list_response.json()["data"]
    assert payload["total"] >= 1
    assert any("躺卧" in item["title"] for item in payload["items"])

    summary_response = client.get("/api/v1/alerts/summary", headers=auth_headers(token))
    assert summary_response.status_code == 200
    assert summary_response.json()["data"]["open_count"] >= 1

    target_alert_id = payload["items"][0]["id"]
    update_response = client.patch(
        f"/api/v1/alerts/{target_alert_id}/status",
        json={"status": "resolved", "handling_note": "已人工复核"},
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    updated_alert = update_response.json()["data"]
    assert updated_alert["status"] == "resolved"
    assert updated_alert["handling_note"] == "已人工复核"


def test_history_queries_and_analysis_cover_behavior_and_alerts(client, monkeypatch) -> None:
    def fake_inference_service(payload: dict[str, object], **_kwargs) -> dict[str, object]:
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        return {
            "request_id": payload["request_id"],
            "service": "cow-monitor-inference",
            "model_name": "stage4-demo-model",
            "model_version": "0.4.0",
            "inference_source": "demo-pipeline",
            "processed_at": datetime.now(UTC).isoformat(),
            "behavior_events": [
                {
                    "device_code": payload["device_code"],
                    "event_time": occurred_at.isoformat(),
                    "behavior_type": "feeding",
                    "cow_count": 4,
                    "confidence": 0.91,
                    "zone_name": "Water Zone",
                    "notes": "阶段四历史分析测试",
                }
            ],
            "raw_metadata": {"pipeline_mode": "demo"},
        }

    monkeypatch.setattr(
        "app.modules.events.router.invoke_inference_service",
        fake_inference_service,
    )

    token = login(client, "admin", "admin123")
    occurred_at = datetime.now(UTC) - timedelta(minutes=130)

    import_response = client.post(
        "/api/v1/events/import",
        json={
            "device_code": "CAM-TEST-001",
            "source_type": "video",
            "source_uri": "demo://tests/stage4-history.mp4",
            "occurred_at": occurred_at.isoformat(),
            "metadata": {},
        },
        headers=auth_headers(token),
    )
    assert import_response.status_code == 200

    history_event_response = client.get(
        "/api/v1/history/behavior-events?behavior_type=feeding&page=1&page_size=10",
        headers=auth_headers(token),
    )
    assert history_event_response.status_code == 200
    history_events = history_event_response.json()["data"]
    assert history_events["total"] == 1

    history_alert_response = client.get(
        "/api/v1/history/alerts?rule_source=preset&page=1&page_size=10",
        headers=auth_headers(token),
    )
    assert history_alert_response.status_code == 200
    history_alerts = history_alert_response.json()["data"]
    assert history_alerts["total"] >= 1
    assert any("饮水区" in item["title"] or "饮水" in item["title"] for item in history_alerts["items"])

    analysis_response = client.get(
        "/api/v1/history/analysis",
        headers=auth_headers(token),
    )
    assert analysis_response.status_code == 200
    analysis = analysis_response.json()["data"]
    assert analysis["total_behavior_events"] == 1
    assert analysis["total_alerts"] >= 1
    assert any(item["label"] == "feeding" or item["label"] == "喂食" or item["label"] == "采食" for item in analysis["behavior_share"])
    assert len(analysis["alert_severity_distribution"]) >= 1
