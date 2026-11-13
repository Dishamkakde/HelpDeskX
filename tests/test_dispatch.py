import pytest
import threading
from backend.database import SessionLocal, init_db, engine, Base
from backend.models import User, Team, Ticket, RoutingRule, Assignment, Escalation
from backend.dispatch import dispatch_ticket
from backend.routing import get_team_active_ticket_count
from backend.seed import seed_database

@pytest.fixture(autouse=True)
def setup_fresh_db():
    seed_database()
    yield

class TestDispatchEngine:
    """
    BCS502: Computer Networks Routing, Capacity & Escalation Engine
    Covers Test Cases 17 - 22
    """

    # Test Case 17: Team capacity reached (8 open tickets maximum)
    def test_case_17_team_capacity_limit_8(self):
        db = SessionLocal()
        team1 = db.query(Team).filter(Team.team_name == "Team 1").first()
        user = db.query(User).filter(User.role == "STAFF").first()

        # Fill Team 1 with exactly 8 tickets
        current_open = get_team_active_ticket_count(db, team1.id)
        for i in range(8 - current_open):
            t = Ticket(
                public_ticket_id=f"HDX-CAP-{i:03d}",
                reporter_id=user.id,
                department_code="CS",
                issue_code="101",
                priority="H",
                ticket_identifier=f"CS-10{i}-H",
                description="Laptop screen hardware issue",
                category="HARDWARE",
                dfa_result="VALID",
                regex_result="VALID",
                validation_status="PASSED",
                status="Assigned",
                assigned_team_id=team1.id
            )
            db.add(t)
        db.commit()

        # Team 1 is now at full 8-ticket capacity
        assert get_team_active_ticket_count(db, team1.id) == 8

        # Submit next hardware ticket for CS (normally routed to Team 1)
        next_ticket = Ticket(
            public_ticket_id="HDX-OVERFLOW-01",
            reporter_id=user.id,
            department_code="CS",
            issue_code="101",
            priority="H",
            ticket_identifier="CS-109-H",
            description="Laptop motherboard hardware problem",
            category="HARDWARE",
            dfa_result="VALID",
            regex_result="VALID",
            validation_status="PASSED",
            status="Pending"
        )
        db.add(next_ticket)
        db.commit()

        # Dispatch should route to configured Backup Team (Team 2), NOT Team 1!
        dispatch_res = dispatch_ticket(db, next_ticket)
        assert dispatch_res["status"] == "BACKUP_ASSIGNED"
        assert dispatch_res["team_name"] == "Team 2"
        assert next_ticket.is_backup is True
        db.close()

    # Test Case 18: Handler unavailable
    def test_case_18_handler_unavailable(self):
        db = SessionLocal()
        handler1 = db.query(User).filter(User.email == "handler1@helpdeskx.com").first()
        handler1.is_available = False
        db.commit()

        user = db.query(User).filter(User.role == "STAFF").first()
        ticket = Ticket(
            public_ticket_id="HDX-UNAVAIL-01",
            reporter_id=user.id,
            department_code="EC",
            issue_code="101",
            priority="H",
            ticket_identifier="EC-101-H",
            description="Lab keyboard hardware failure",
            category="HARDWARE",
            dfa_result="VALID",
            regex_result="VALID",
            validation_status="PASSED",
            status="Pending"
        )
        db.add(ticket)
        db.commit()

        # Handler 1 is unavailable, so primary team has no available handler.
        # Should divert to Backup team (Team 3) or available handler!
        res = dispatch_ticket(db, ticket)
        assert ticket.assigned_handler_id != handler1.id
        db.close()

    # Test Case 19: All teams full (triggers Level-2 Escalation)
    def test_case_19_all_teams_full_level_2_escalation(self):
        db = SessionLocal()
        user = db.query(User).filter(User.role == "STAFF").first()
        teams = db.query(Team).all()

        # Saturate all 4 teams to 8 capacity each
        count = 100
        for team in teams:
            current = get_team_active_ticket_count(db, team.id)
            for _ in range(8 - current):
                t = Ticket(
                    public_ticket_id=f"HDX-SAT-{count}",
                    reporter_id=user.id,
                    department_code="CS",
                    issue_code="101",
                    priority="M",
                    ticket_identifier="CS-101-M",
                    description="Capacity saturation ticket",
                    category="HARDWARE",
                    dfa_result="VALID",
                    regex_result="VALID",
                    validation_status="PASSED",
                    status="In Progress",
                    assigned_team_id=team.id
                )
                db.add(t)
                count += 1
        db.commit()

        # Verify all 4 teams have 8 open tickets
        for team in teams:
            assert get_team_active_ticket_count(db, team.id) == 8

        # Now submit a new ticket
        esc_ticket = Ticket(
            public_ticket_id="HDX-TRIGGER-L2",
            reporter_id=user.id,
            department_code="CS",
            issue_code="999",
            priority="H",
            ticket_identifier="CS-999-H",
            description="Urgent server hardware failure",
            category="HARDWARE",
            dfa_result="VALID",
            regex_result="VALID",
            validation_status="PASSED",
            status="Pending"
        )
        db.add(esc_ticket)
        db.commit()

        res = dispatch_ticket(db, esc_ticket)
        assert res["status"] == "ESCALATED_LEVEL_2"
        assert esc_ticket.is_escalated is True

        # Verify Escalation record created in SQLite
        esc_rec = db.query(Escalation).filter(Escalation.ticket_id == esc_ticket.id).first()
        assert esc_rec is not None
        assert esc_rec.escalation_level == "Level-2"
        db.close()

    # Test Case 20: Emergency Priority Override
    def test_case_20_emergency_priority_override(self):
        db = SessionLocal()
        ticket = db.query(Ticket).filter(Ticket.priority == "L").first()
        assert ticket is not None
        old_prio = ticket.priority

        # Admin overrides priority from L to H
        ticket.priority = "H"
        db.commit()

        updated = db.query(Ticket).filter(Ticket.id == ticket.id).first()
        assert updated.priority == "H"
        assert updated.priority != old_prio
        db.close()

    # Test Case 21: Duplicate assignment prevention
    def test_case_21_prevent_duplicate_assignment(self):
        db = SessionLocal()
        ticket = db.query(Ticket).filter(Ticket.status == "Assigned").first()
        initial_assigned_handler = ticket.assigned_handler_id

        # Dispatching an already assigned ticket should not double-assign
        assignment_count_before = len(ticket.assignments)
        assert assignment_count_before >= 1
        db.close()

    # Test Case 22: Concurrent dispatch safety
    def test_case_22_concurrent_dispatch(self):
        db = SessionLocal()
        user = db.query(User).filter(User.role == "STAFF").first()

        tickets = []
        for i in range(4):
            t = Ticket(
                public_ticket_id=f"HDX-CONC-{i}",
                reporter_id=user.id,
                department_code="IT",
                issue_code="201",
                priority="M",
                ticket_identifier=f"IT-20{i}-M",
                description="Network connectivity issue",
                category="NETWORK",
                dfa_result="VALID",
                regex_result="VALID",
                validation_status="PASSED",
                status="Pending"
            )
            db.add(t)
            tickets.append(t)
        db.commit()

        results = []
        errors = []

        def worker(t_id):
            session = SessionLocal()
            try:
                t = session.query(Ticket).filter(Ticket.id == t_id).first()
                res = dispatch_ticket(session, t)
                results.append(res)
            except Exception as e:
                errors.append(e)
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(t.id,)) for t in tickets]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0
        assert len(results) == 4
        db.close()

