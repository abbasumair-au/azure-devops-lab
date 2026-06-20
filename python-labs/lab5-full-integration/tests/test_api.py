class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_body(self, client):
        data = client.get("/api/v1/health").get_json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"


class TestListResources:
    def test_list_all(self, client):
        data = client.get("/api/v1/resources").get_json()
        assert "resources" in data
        assert "count" in data
        assert data["count"] == len(data["resources"])

    def test_filter_by_type(self, client):
        data = client.get("/api/v1/resources?type=VirtualMachine").get_json()
        assert all(r["type"] == "VirtualMachine" for r in data["resources"])

    def test_filter_by_region(self, client):
        data = client.get("/api/v1/resources?region=eastus").get_json()
        assert all(r["region"] == "eastus" for r in data["resources"])

    def test_filter_compliant_true(self, client):
        data = client.get("/api/v1/resources?compliant=true").get_json()
        assert all(r["compliant"] is True for r in data["resources"])

    def test_filter_compliant_false(self, client):
        data = client.get("/api/v1/resources?compliant=false").get_json()
        assert all(r["compliant"] is False for r in data["resources"])

    def test_combined_filters(self, client):
        data = client.get("/api/v1/resources?type=VirtualMachine&region=eastus").get_json()
        assert data["count"] == 1
        assert data["resources"][0]["id"] == "vm-001"


class TestGetResource:
    def test_existing_resource(self, client):
        resp = client.get("/api/v1/resources/vm-001")
        assert resp.status_code == 200
        assert resp.get_json()["id"] == "vm-001"

    def test_nonexistent_resource(self, client):
        resp = client.get("/api/v1/resources/nonexistent")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_unknown_route(self, client):
        assert client.get("/api/v1/unknown").status_code == 404
