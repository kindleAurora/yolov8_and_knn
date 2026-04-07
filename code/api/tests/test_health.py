def test_health_endpoint_returns_stage_three_payload(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["code"] == 0
    assert payload["data"]["service"] == "cow-monitor-api"
    assert payload["data"]["phase"] == "stage-3"
