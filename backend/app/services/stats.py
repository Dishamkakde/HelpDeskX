import sqlite3
import os
from typing import Dict, Any, List
from ..database import get_db, get_db_path

def get_dashboard_statistics() -> Dict[str, Any]:
    """
    Computes real-time analytics strictly from the SQLite database.
    Used to populate all charts, counters, and gauges on the dashboard.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Ticket Status Breakdown
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) as resolved_count,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed_count,
                SUM(CASE WHEN status = 'ESCALATED' OR is_escalated = 1 THEN 1 ELSE 0 END) as escalated_count,
                SUM(CASE WHEN is_backup_assigned = 1 THEN 1 ELSE 0 END) as backup_count,
                SUM(CASE WHEN priority_overridden = 1 THEN 1 ELSE 0 END) as override_count
            FROM tickets
        """)
        row = cursor.fetchone()
        total = row["total"] or 0
        overview = {
            "total_tickets": total,
            "open_tickets": row["open_count"] or 0,
            "in_progress_tickets": row["in_progress_count"] or 0,
            "resolved_tickets": row["resolved_count"] or 0,
            "closed_tickets": row["closed_count"] or 0,
            "escalated_tickets": row["escalated_count"] or 0,
            "backup_assigned_tickets": row["backup_count"] or 0,
            "priority_overridden_tickets": row["override_count"] or 0
        }

        # 2. Category Breakdown
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM tickets
            GROUP BY category
            ORDER BY count DESC
        """)
        cat_rows = cursor.fetchall()
        category_breakdown = []
        for r in cat_rows:
            cnt = r["count"]
            pct = round((cnt / total * 100), 1) if total > 0 else 0
            category_breakdown.append({
                "category": r["category"],
                "count": cnt,
                "percentage": pct
            })

        # Ensure all 5 categories are present even if count is 0
        present_cats = {c["category"] for c in category_breakdown}
        all_five = ["HARDWARE", "SOFTWARE", "NETWORK", "ACCESS_SECURITY", "BILLING_ACCOUNT"]
        for cat in all_five:
            if cat not in present_cats:
                category_breakdown.append({
                    "category": cat,
                    "count": 0,
                    "percentage": 0.0
                })

        # 3. Priority Distribution
        cursor.execute("""
            SELECT priority, COUNT(*) as count
            FROM tickets
            GROUP BY priority
        """)
        priority_rows = cursor.fetchall()
        priority_map = {r["priority"]: r["count"] for r in priority_rows}
        priority_distribution = {
            "CRITICAL": priority_map.get("CRITICAL", 0),
            "HIGH": priority_map.get("HIGH", 0),
            "MEDIUM": priority_map.get("MEDIUM", 0),
            "LOW": priority_map.get("LOW", 0)
        }

        # 4. Agent Workload & 8-Ticket Capacity Gauges
        cursor.execute("""
            SELECT 
                a.id as agent_id,
                a.name as agent_name,
                a.role,
                a.max_active_tickets,
                a.is_active,
                t.name as team_name,
                t.category as team_category,
                COUNT(tk.id) as active_tickets
            FROM agents a
            JOIN teams t ON a.team_id = t.id
            LEFT JOIN tickets tk ON a.id = tk.assigned_agent_id 
                AND tk.status IN ('OPEN', 'IN_PROGRESS', 'ESCALATED')
            GROUP BY a.id
            ORDER BY active_tickets DESC, a.name ASC
        """)
        agent_rows = cursor.fetchall()
        agent_workloads = []
        for a in agent_rows:
            limit = a["max_active_tickets"] or 8
            active = a["active_tickets"] or 0
            utilization = round((active / limit * 100), 1) if limit > 0 else 0
            agent_workloads.append({
                "agent_id": a["agent_id"],
                "agent_name": a["agent_name"],
                "team_name": a["team_name"],
                "role": a["role"],
                "active_tickets": active,
                "max_capacity": limit,
                "utilization_pct": utilization,
                "is_at_capacity": active >= limit,
                "is_active": bool(a["is_active"])
            })

        # 5. Classifier Metrics
        cursor.execute("""
            SELECT 
                classifier_used,
                COUNT(*) as count,
                AVG(classifier_confidence) as avg_confidence
            FROM tickets
            GROUP BY classifier_used
        """)
        clf_rows = cursor.fetchall()
        classifier_metrics = [
            {
                "classifier": r["classifier_used"],
                "count": r["count"],
                "avg_confidence": round(r["avg_confidence"] or 0, 3)
            }
            for r in clf_rows
        ]

        # 6. Recent Audit Logs
        cursor.execute("""
            SELECT 
                l.id,
                l.ticket_id,
                t.ticket_number,
                l.action,
                l.performed_by,
                l.details,
                l.timestamp
            FROM ticket_logs l
            JOIN tickets t ON l.ticket_id = t.id
            ORDER BY l.id DESC
            LIMIT 15
        """)
        log_rows = cursor.fetchall()
        recent_logs = [dict(r) for r in log_rows]

        # 7. Database Engine Health
        db_path = get_db_path()
        db_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0

        return {
            "overview": overview,
            "category_breakdown": category_breakdown,
            "priority_distribution": priority_distribution,
            "agent_workloads": agent_workloads,
            "classifier_metrics": classifier_metrics,
            "recent_logs": recent_logs,
            "database_health": {
                "db_path": db_path,
                "db_size_kb": db_size_kb,
                "total_agents": len(agent_workloads),
                "total_teams": len({a["team_name"] for a in agent_workloads})
            }
        }
