from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import Escalation, Ticket, Team, User, StatusHistory

def get_all_escalations(db: Session) -> List[Dict[str, Any]]:
    escalations = db.query(Escalation).order_by(Escalation.id.desc()).all()
    results = []
    for esc in escalations:
        item = esc.to_dict()
        if esc.ticket:
            item["ticket_identifier"] = esc.ticket.ticket_identifier
            item["department_code"] = esc.ticket.department_code
            item["priority"] = esc.ticket.priority
            item["category"] = esc.ticket.category
            item["status"] = esc.ticket.status
        results.append(item)
    return results

def resolve_escalation(
    db: Session,
    escalation_id: int,
    action: str,
    target_team_id: Optional[int] = None,
    target_handler_id: Optional[int] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    esc = db.query(Escalation).filter(Escalation.id == escalation_id).first()
    if not esc:
        raise ValueError(f"Escalation #{escalation_id} not found.")

    ticket = esc.ticket
    esc.status = "Resolved by L2 Supervisor"

    if action == "REASSIGN" and target_team_id:
        ticket.assigned_team_id = target_team_id
        ticket.assigned_handler_id = target_handler_id
        ticket.status = "Assigned"
        ticket.is_escalated = False
        log_notes = f"L2 Supervisor reassigned ticket to Team #{target_team_id}. Notes: {notes or 'None'}"
    else:
        ticket.status = "Resolved"
        ticket.is_escalated = False
        log_notes = f"L2 Supervisor resolved escalated ticket directly. Notes: {notes or 'Direct L2 resolution'}"

    history = StatusHistory(
        ticket_id=ticket.id,
        previous_status="Escalated",
        new_status=ticket.status,
        changed_by="L2_SUPERVISOR",
        notes=log_notes
    )
    db.add(history)
    db.commit()

    return {
        "escalation_id": escalation_id,
        "ticket_id": ticket.id,
        "new_status": ticket.status,
        "message": log_notes
    }

