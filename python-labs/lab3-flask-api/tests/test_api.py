import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import app, _metrics


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _metrics["requests_total"] = 0
    _metrics["errors_total"] = 0
    with app.test_client() as client:
        yield client


class TestHealth:
    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_status_is_ok(self, client):
        data = client.get("/health").get_json()
        assert data["status"] == "ok"

    def test_has_timestamp(self, client):
        data = client.get("/health").get_json()
        assert "timestamp" in data


class TestMetrics:
    def test_returns_200(self, client):
        assert client.get("/metrics").status_code == 200

    def test_has_required_fields(self, client):
        data = client.get("/metrics").get_json()
        assert "requests_total" in data
        assert "errors_total" in data
        assert "uptime_start" in data


class TestWebhook:
    def test_valid_webhook_200(self, client):
        resp = client.post("/webhook", json={"event_type": "policy_violation"})
        assert resp.status_code == 200

    def test_valid_webhook_response_body(self, client):
        data = client.post("/webhook", json={"event_type": "policy_violation"}).get_json()
        assert data["status"] == "received"
        assert data["event_type"] == "policy_violation"

    def test_missing_event_type_400(self, client):
        resp = client.post("/webhook", json={"payload": {}})
        assert resp.status_code == 400
        assert "event_type" in resp.get_json()["error"]

    def test_non_json_body_400(self, client):
        resp = client.post("/webhook", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_increments_counter(self, client):
        initial = _metrics["requests_total"]
        client.post("/webhook", json={"event_type": "test"})
        assert _metrics["requests_total"] == initial + 1

    def test_get_method_not_allowed(self, client):
        assert client.get("/webhook").status_code == 405


class TestErrorHandlers:
    def test_unknown_route_404(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        assert "error" in resp.get_json()
