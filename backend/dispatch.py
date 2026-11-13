import threading
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import Ticket, Team, User, Assignment, StatusHistory, Escalation
from .routing import find_routing_rule, get_team_active_ticket_count, get_handler_active_ticket_count

# Thread lock for concurrency protection during dispatch operations
dispatch_lock = threading.Lock()

def dispatch_ticket(db: Session, ticket: Ticket) -> Dict[str, Any]:
    """
    Core Dispatch Engine:
    - Consults Department + Category Routing Table
    - Enforces 8-ticket team capacity
    - Applies Round-Robin across available handlers
    - Falls back to Backup Team on capacity breach
    - Escalates to Level-2 when all teams are saturated
    - Thread-safe and atomic database operations
    """
    with dispatch_lock:
        dept = ticket.department_code
        cat = ticket.category
        rule = find_routing_rule(db, dept, cat)

        if not rule:
            # Fallback queue
            rule = db.query(find_routing_rule(db, "ANY", "OTHER"))

        primary_team = rule.primary_team if rule else None
        backup_team = rule.backup_team if rule else None

        # Helper to find handler via round-robin in a team
        def select_handler_round_robin(team: Team) -> Optional[User]:
            handlers = db.query(User).filter(
                User.team_id == team.id,
                User.role == "HANDLER",
                User.is_available == True
            ).order_by(User.id.asc()).all()

            if not handlers:
                return None

            pointer = team.round_robin_pointer or 0
            idx = pointer % len(handlers)
            selected = handlers[idx]

            # Advance persistent round-robin pointer in DB
            team.round_robin_pointer = (pointer + 1) % len(handlers)
            db.add(team)
            return selected

        # 1. Attempt Primary Team Assignment
        if primary_team and primary_team.is_available:
            active_count = get_team_active_ticket_count(db, primary_team.id)
            if active_count < primary_team.max_capacity:
                handler = select_handler_round_robin(primary_team)
                if handler:
                    ticket.assigned_team_id = primary_team.id
                    ticket.assigned_handler_id = handler.id
                    ticket.status = "Assigned"
                    ticket.is_backup = False
                    ticket.is_escalated = False

                    assignment = Assignment(
                        ticket_id=ticket.id,
                        team_id=primary_team.id,
                        handler_id=handler.id,
                        assignment_type="PRIMARY_ROUND_ROBIN",
                        assignment_reason=f"Routed by rule {dept}+{cat} to {primary_team.team_name} via round-robin."
                    )
                    db.add(assignment)

                    history = StatusHistory(
                        ticket_id=ticket.id,
                        previous_status="Pending",
                        new_status="Assigned",
                        changed_by="AUTO_DISPATCH_ENGINE",
                        notes=f"Assigned to {handler.name} ({primary_team.team_name})."
                    )
                    db.add(history)
                    db.commit()

                    return {
                        "status": "ASSIGNED",
                        "team_id": primary_team.id,
                        "team_name": primary_team.team_name,
                        "handler_id": handler.id,
                        "handler_name": handler.name,
                        "type": "PRIMARY"
                    }

        # 2. Primary is full (>= 8) or unavailable -> Try Backup Team
        if backup_team and backup_team.is_available:
            backup_active = get_team_active_ticket_count(db, backup_team.id)
            if backup_active < backup_team.max_capacity:
                handler = select_handler_round_robin(backup_team)
                if handler:
                    ticket.assigned_team_id = backup_team.id
                    ticket.assigned_handler_id = handler.id
                    ticket.status = "Assigned"
                    ticket.is_backup = True
                    ticket.is_escalated = False

                    reason = f"Primary team '{primary_team.team_name if primary_team else 'None'}' reached 8-ticket capacity or unavailable. Routed to Backup team '{backup_team.team_name}'."
                    assignment = Assignment(
                        ticket_id=ticket.id,
                        team_id=backup_team.id,
                        handler_id=handler.id,
                        assignment_type="BACKUP_ASSIGNMENT",
                        assignment_reason=reason
                    )
                    db.add(assignment)

                    history = StatusHistory(
                        ticket_id=ticket.id,
                        previous_status="Pending",
                        new_status="Assigned",
                        changed_by="AUTO_DISPATCH_ENGINE",
                        notes=reason
                    )
                    db.add(history)
                    db.commit()

                    return {
                        "status": "BACKUP_ASSIGNED",
                        "team_id": backup_team.id,
                        "team_name": backup_team.team_name,
                        "handler_id": handler.id,
                        "handler_name": handler.name,
                        "type": "BACKUP",
                        "reason": reason
                    }

        # 3. Both Primary and Backup Saturated / Unavailable -> Check All Teams
        all_teams = db.query(Team).order_by(Team.id.asc()).all()
        for alt_team in all_teams:
            if alt_team.is_available:
                alt_active = get_team_active_ticket_count(db, alt_team.id)
                if alt_active < alt_team.max_capacity:
                    handler = select_handler_round_robin(alt_team)
                    if handler:
                        ticket.assigned_team_id = alt_team.id
                        ticket.assigned_handler_id = handler.id
                        ticket.status = "Assigned"
                        ticket.is_backup = True

                        reason = f"Configured teams saturated. Assigned to alternate available team '{alt_team.team_name}'."
                        assignment = Assignment(
                            ticket_id=ticket.id,
                            team_id=alt_team.id,
                            handler_id=handler.id,
                            assignment_type="ALTERNATE_ASSIGNMENT",
                            assignment_reason=reason
                        )
                        db.add(assignment)
                        db.commit()
                        return {
                            "status": "ALTERNATE_ASSIGNED",
                            "team_id": alt_team.id,
                            "team_name": alt_team.team_name,
                            "handler_id": handler.id,
                            "handler_name": handler.name,
                            "type": "ALTERNATE"
                        }

        # 4. ALL 4 TEAMS SATURATED AT 8-TICKET CAPACITY -> LEVEL-2 ESCALATION!
        ticket.is_escalated = True
        ticket.status = "Pending"  # Remains pending in Level-2 Escalation queue
        ticket.assigned_team_id = None
        ticket.assigned_handler_id = None

        esc_reason = f"All helpdesk teams reached maximum capacity of {primary_team.max_capacity if primary_team else 8} open tickets or unavailable. Escalated to Level-2."
        escalation = Escalation(
            ticket_id=ticket.id,
            escalation_level="Level-2",
            reason=esc_reason,
            status="Pending L2 Review"
        )
        db.add(escalation)

        history = StatusHistory(
            ticket_id=ticket.id,
            previous_status="Pending",
            new_status="Pending",
            changed_by="AUTO_DISPATCH_ENGINE",
            notes=f"ESCALATION TRIGGERED: {esc_reason}"
        )
        db.add(history)
        db.commit()

        return {
            "status": "ESCALATED_LEVEL_2",
            "team_id": None,
            "handler_id": None,
            "type": "LEVEL_2",
            "reason": esc_reason
        }

