import pytest
import json
from backend.app import app
from backend.database import SessionLocal, init_db
from backend.models import User, Ticket, StatusHistory
from backend.seed import seed_database

@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    seed_database()
    with app.test_client() as client:
        yield client

class TestAPIAndPersistence:
    """
    Covers Test Cases 23 - 24:
    Status Management Transitions, REST API Endpoints, and SQLite Persistence
    """

    # Test Case 23: Status update valid transitions
    def test_case_23_status_transitions(self, client):
        # 1. Login as Admin to get token
        login_res = client.post("/api/auth/login", json={
            "email": "admin@helpdeskx.com",
            "password": "Admin@123"
        })
        assert login_res.status_code == 200
        token = login_res.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get first ticket
        tickets_res = client.get("/api/tickets", headers=headers)
        assert tickets_res.status_code == 200
        tickets = tickets_res.get_json()
        assert len(tickets) > 0
        t_id = tickets[0]["id"]

        # 3. Valid transition: Update to 'In Progress'
        patch_res = client.patch(f"/api/tickets/{t_id}/status", json={
            "status": "In Progress",
            "notes": "Investigation initiated by support."
        }, headers=headers)
        assert patch_res.status_code == 200
        assert patch_res.get_json()["ticket"]["status"] == "In Progress"

        # 4. Valid transition: Update to 'Resolved'
        resolve_res = client.patch(f"/api/tickets/{t_id}/status", json={
            "status": "Resolved",
            "notes": "Resolved by replacing faulty component."
        }, headers=headers)
        assert resolve_res.status_code == 200
        assert resolve_res.get_json()["ticket"]["status"] == "Resolved"

        # 5. Invalid status check
        invalid_res = client.patch(f"/api/tickets/{t_id}/status", json={
            "status": "NON_EXISTENT_STATUS"
        }, headers=headers)
        assert invalid_res.status_code == 400

    # Test Case 24: Database persistence across sessions and API endpoints
    def test_case_24_database_persistence_and_endpoints(self, client):
        headers = {"X-User-Role": "ADMIN"}

        # Health endpoint
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.get_json()["status"] == "healthy"

        # DFA Spec endpoint
        spec = client.get("/api/dfa/spec")
        assert spec.status_code == 200
        assert "Q" in spec.get_json()

        # Validation endpoint
        val_res = client.post("/api/validate", json={"identifier": "CS-101-H"})
        assert val_res.status_code == 200
        assert val_res.get_json()["is_valid"] is True

        # Classification endpoint
        clf_res = client.post("/api/classify", json={"description": "My laptop monitor won't turn on."})
        assert clf_res.status_code == 200
        assert clf_res.get_json()["category"] == "HARDWARE"

        # Submit new ticket via API
        sub_res = client.post("/api/tickets", json={
            "reporter_name": "Test Engineer",
            "email": "test.engineer@helpdeskx.com",
            "department": "IT",
            "ticket_identifier": "IT-201-H",
            "description": "Critical router gateway offline in server room network failure"
        }, headers=headers)
        assert sub_res.status_code == 201
        created_ticket = sub_res.get_json()["ticket"]
        assert created_ticket["category"] == "NETWORK"
        assert created_ticket["status"] == "Assigned"

        # Verify persistent read from database via separate query
        db = SessionLocal()
        saved = db.query(Ticket).filter(Ticket.id == created_ticket["id"]).first()
        assert saved is not None
        assert saved.category == "NETWORK"
        assert saved.priority == "H"
        db.close()

        # Verify Analytics endpoint computes live data
        analytics_res = client.get("/api/analytics", headers=headers)
        assert analytics_res.status_code == 200
        metrics = analytics_res.get_json()
        assert metrics["overview"]["total_tickets"] > 0
        assert len(metrics["team_workload"]) == 4

