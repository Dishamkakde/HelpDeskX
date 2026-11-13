import pytest
from backend.database import SessionLocal, init_db
from backend.routing import find_routing_rule

@pytest.fixture(scope="module")
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

class TestRoutingTable:
    """
    BCS502: Computer Networks Routing Table Verification
    Covers Test Cases 15 - 16
    """

    # Test Case 15: Configured Department + Category Lookups
    def test_case_15_configured_routes(self, db_session):
        rule_cs_hw = find_routing_rule(db_session, "CS", "HARDWARE")
        assert rule_cs_hw is not None
        assert rule_cs_hw.primary_team.team_name == "Team 1"

        rule_cs_sw = find_routing_rule(db_session, "CS", "SOFTWARE")
        assert rule_cs_sw is not None
        assert rule_cs_sw.primary_team.team_name == "Team 2"

        rule_it_net = find_routing_rule(db_session, "IT", "NETWORK")
        assert rule_it_net is not None
        assert rule_it_net.primary_team.team_name == "Team 3"

        rule_hr_acc = find_routing_rule(db_session, "HR", "ACCESS")
        assert rule_hr_acc is not None
        assert rule_hr_acc.primary_team.team_name == "Team 4"

    # Test Case 16: Unknown department and unknown routing key fallback
    def test_case_16_unknown_routing_fallback(self, db_session):
        # Unknown department 'ZZ' with unknown category 'OTHER'
        # Must resolve to central fallback queue rule (ANY + OTHER)
        fallback_rule = find_routing_rule(db_session, "ZZ", "OTHER")
        assert fallback_rule is not None
        assert fallback_rule.primary_team is not None

