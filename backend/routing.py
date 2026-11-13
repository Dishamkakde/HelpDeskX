from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from .models import RoutingRule, Team, Ticket, User

DEFAULT_ROUTING_MAP = [
    # Dept, Category, Primary Team, Backup Team
    ("CS", "HARDWARE", "Team 1", "Team 2"),
    ("CS", "SOFTWARE", "Team 2", "Team 1"),
    ("IT", "NETWORK", "Team 3", "Team 4"),
    ("HR", "ACCESS", "Team 4", "Team 2"),
    ("EC", "HARDWARE", "Team 1", "Team 3"),
    ("EC", "NETWORK", "Team 3", "Team 1"),
    ("ANY", "OTHER", "Team 4", "Team 1"),
]

def find_routing_rule(db: Session, dept_code: str, category: str) -> Optional[RoutingRule]:
    """
    Looks up routing rule matching department code and category.
    Falls back to ANY + category or ANY + OTHER.
    """
    rule = db.query(RoutingRule).filter(
        RoutingRule.department_code == dept_code.upper(),
        RoutingRule.category == category.upper(),
        RoutingRule.is_active == True
    ).first()

    if not rule:
        # Check wildcard ANY for the department
        rule = db.query(RoutingRule).filter(
            RoutingRule.department_code == "ANY",
            RoutingRule.category == category.upper(),
            RoutingRule.is_active == True
        ).first()

    if not rule:
        # Check fallback ANY + OTHER
        rule = db.query(RoutingRule).filter(
            RoutingRule.department_code == "ANY",
            RoutingRule.category == "OTHER",
            RoutingRule.is_active == True
        ).first()

    return rule

def get_team_active_ticket_count(db: Session, team_id: int) -> int:
    """
    Counts OPEN tickets for team: Pending, Assigned, In Progress.
    Resolved tickets do NOT count toward capacity.
    """
    return db.query(Ticket).filter(
        Ticket.assigned_team_id == team_id,
        Ticket.status.in_(["Pending", "Assigned", "In Progress"])
    ).count()

def get_handler_active_ticket_count(db: Session, handler_id: int) -> int:
    return db.query(Ticket).filter(
        Ticket.assigned_handler_id == handler_id,
        Ticket.status.in_(["Pending", "Assigned", "In Progress"])
    ).count()

