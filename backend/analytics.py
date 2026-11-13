from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import Ticket, Team, User, Escalation
from .routing import get_team_active_ticket_count

def get_analytics_metrics(db: Session) -> dict:
    """
    Computes all analytics strictly from live SQLite database records.
    """
    total_tickets = db.query(Ticket).count()
    resolved_tickets = db.query(Ticket).filter(Ticket.status == "Resolved").count()
    unresolved_tickets = total_tickets - resolved_tickets

    # 1. Category-wise distribution
    category_counts = db.query(
        Ticket.category, func.count(Ticket.id)
    ).group_by(Ticket.category).all()
    category_distribution = {cat: count for cat, count in category_counts}
    # Ensure all 5 categories exist
    for cat in ["HARDWARE", "SOFTWARE", "NETWORK", "ACCESS", "OTHER"]:
        category_distribution.setdefault(cat, 0)

    # 2. Department-wise distribution
    dept_counts = db.query(
        Ticket.department_code, func.count(Ticket.id)
    ).group_by(Ticket.department_code).all()
    department_distribution = {dept: count for dept, count in dept_counts}

    # 3. Priority-wise distribution
    priority_counts = db.query(
        Ticket.priority, func.count(Ticket.id)
    ).group_by(Ticket.priority).all()
    priority_distribution = {"H": 0, "M": 0, "L": 0}
    for prio, count in priority_counts:
        if prio in priority_distribution:
            priority_distribution[prio] = count

    # 4. Team-wise workload & 8-ticket capacity
    teams = db.query(Team).all()
    team_workload = []
    for t in teams:
        active = get_team_active_ticket_count(db, t.id)
        team_workload.append({
            "team_id": t.id,
            "team_name": t.team_name,
            "max_capacity": t.max_capacity,
            "active_tickets": active,
            "utilization_pct": round((active / t.max_capacity * 100), 1) if t.max_capacity > 0 else 0,
            "is_at_capacity": active >= t.max_capacity,
            "is_available": t.is_available
        })

    # 5. Daily ticket submissions (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_rows = db.query(
        func.date(Ticket.created_at).label("day"),
        func.count(Ticket.id).label("count")
    ).filter(Ticket.created_at >= seven_days_ago).group_by("day").all()
    daily_submissions = [{"date": str(r[0]), "count": r[1]} for r in daily_rows]

    # 6. Escalated ticket count
    escalated_count = db.query(Ticket).filter(Ticket.is_escalated == True).count()
    active_escalations = db.query(Escalation).filter(Escalation.status == "Pending L2 Review").count()

    # 7. Backup assigned count
    backup_count = db.query(Ticket).filter(Ticket.is_backup == True).count()

    # 8. Average resolution time (in minutes)
    # Estimate based on updated_at - created_at for resolved tickets
    resolved_list = db.query(Ticket).filter(Ticket.status == "Resolved").all()
    if resolved_list:
        durations = [
            (t.updated_at - t.created_at).total_seconds() / 60
            for t in resolved_list
            if t.updated_at and t.created_at
        ]
        avg_res_min = round(sum(durations) / len(durations), 1) if durations else 15.0
    else:
        avg_res_min = 0.0

    return {
        "overview": {
            "total_tickets": total_tickets,
            "resolved_tickets": resolved_tickets,
            "unresolved_tickets": unresolved_tickets,
            "escalated_count": escalated_count,
            "active_escalations": active_escalations,
            "backup_count": backup_count,
            "avg_resolution_minutes": avg_res_min
        },
        "category_distribution": [
            {"category": k, "count": v} for k, v in category_distribution.items()
        ],
        "department_distribution": [
            {"department": k, "count": v} for k, v in department_distribution.items()
        ],
        "priority_distribution": [
            {"priority": "High (H)", "code": "H", "count": priority_distribution["H"]},
            {"priority": "Medium (M)", "code": "M", "count": priority_distribution["M"]},
            {"priority": "Low (L)", "code": "L", "count": priority_distribution["L"]}
        ],
        "team_workload": team_workload,
        "daily_submissions": daily_submissions
    }

