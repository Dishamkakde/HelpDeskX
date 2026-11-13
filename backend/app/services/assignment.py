import sqlite3
import asyncio
from typing import Dict, Any, Optional, Tuple
from ..database import get_db

# Asynchronous lock for concurrency safety during ticket creation and assignment
assignment_lock = asyncio.Lock()

TEAM_CATEGORY_MAP = {
    "HARDWARE": "Hardware Support",
    "SOFTWARE": "Software Engineering",
    "NETWORK": "Network Operations",
    "ACCESS_SECURITY": "Security & Access",
    "BILLING_ACCOUNT": "Billing & Finance"
}

def get_agent_active_ticket_count(cursor: sqlite3.Cursor, agent_id: int) -> int:
    cursor.execute("""
        SELECT COUNT(*) as active_count
        FROM tickets
        WHERE assigned_agent_id = ?
          AND status IN ('OPEN', 'IN_PROGRESS', 'ESCALATED')
    """, (agent_id,))
    row = cursor.fetchone()
    return row["active_count"] if row else 0

def find_candidate_agent(
    cursor: sqlite3.Cursor,
    team_id: int,
    max_capacity: int = 8
) -> Tuple[Optional[sqlite3.Row], int]:
    """
    Finds candidate agent using Round-Robin logic while respecting the 8-ticket capacity.
    Returns: (agent_row, new_rr_index) or (None, current_rr_index) if all agents at capacity.
    """
    cursor.execute("""
        SELECT current_rr_index FROM teams WHERE id = ?
    """, (team_id,))
    team_row = cursor.fetchone()
    current_rr_index = team_row["current_rr_index"] if team_row else 0

    cursor.execute("""
        SELECT id, name, email, max_active_tickets
        FROM agents
        WHERE team_id = ? AND is_active = 1
        ORDER BY id ASC
    """, (team_id,))
    agents = cursor.fetchall()

    if not agents:
        return None, current_rr_index

    total_agents = len(agents)
    
    # Try round-robin starting from current_rr_index
    for attempt in range(total_agents):
        idx = (current_rr_index + attempt) % total_agents
        candidate = agents[idx]
        limit = candidate["max_active_tickets"] or max_capacity
        active_count = get_agent_active_ticket_count(cursor, candidate["id"])

        if active_count < limit:
            # Advance RR index to the next agent for subsequent submissions
            next_rr_index = (idx + 1) % total_agents
            return candidate, next_rr_index

    # All agents in this team are at capacity (>= 8 active tickets)
    return None, current_rr_index

def dispatch_ticket(
    cursor: sqlite3.Cursor,
    category: str,
    priority: str
) -> Dict[str, Any]:
    """
    Core assignment algorithm:
    1. Primary Team Round-Robin (Cap = 8)
    2. Backup Team Assignment (if primary at capacity)
    3. Level-2 Escalation (if backup at capacity or priority is CRITICAL)
    """
    primary_team_name = TEAM_CATEGORY_MAP.get(category, "Hardware Support")
    
    cursor.execute("SELECT id, name, max_capacity FROM teams WHERE name = ?", (primary_team_name,))
    primary_team = cursor.fetchone()
    
    if not primary_team:
        raise ValueError(f"Primary team for category '{category}' not found.")

    primary_team_id = primary_team["id"]
    team_capacity = primary_team["max_capacity"] or 8

    # 1. Attempt Primary Round-Robin Assignment
    chosen_agent, new_rr = find_candidate_agent(cursor, primary_team_id, team_capacity)
    
    if chosen_agent:
        cursor.execute("UPDATE teams SET current_rr_index = ? WHERE id = ?", (new_rr, primary_team_id))
        return {
            "assigned_agent_id": chosen_agent["id"],
            "assigned_team_id": primary_team_id,
            "status": "OPEN",
            "is_escalated": 0,
            "escalation_reason": None,
            "is_backup_assigned": 0,
            "assignment_type": "PRIMARY_ROUND_ROBIN",
            "details": f"Assigned via round-robin to {chosen_agent['name']} ({primary_team_name})."
        }

    # 2. Primary Team is at 8-Ticket Capacity! Attempt Backup Assignment
    cursor.execute("SELECT id, name, max_capacity FROM teams WHERE name = 'General Backup'")
    backup_team = cursor.fetchone()

    if backup_team:
        backup_agent, backup_rr = find_candidate_agent(cursor, backup_team["id"], backup_team["max_capacity"] or 8)
        if backup_agent and priority != "CRITICAL":
            cursor.execute("UPDATE teams SET current_rr_index = ? WHERE id = ?", (backup_rr, backup_team["id"]))
            return {
                "assigned_agent_id": backup_agent["id"],
                "assigned_team_id": backup_team["id"],
                "status": "OPEN",
                "is_escalated": 0,
                "escalation_reason": None,
                "is_backup_assigned": 1,
                "assignment_type": "BACKUP_ASSIGNED",
                "details": f"Primary team '{primary_team_name}' reached 8-ticket capacity. Routed to Backup Agent {backup_agent['name']}."
            }

    # 3. Backup Team is ALSO at capacity, OR Priority is CRITICAL -> Escalate to Level-2!
    cursor.execute("SELECT id, name FROM teams WHERE name = 'Level-2 Escalations'")
    l2_team = cursor.fetchone()
    l2_team_id = l2_team["id"] if l2_team else primary_team_id

    # Select L2 specialist
    cursor.execute("""
        SELECT id, name FROM agents WHERE team_id = ? AND is_active = 1 LIMIT 1
    """, (l2_team_id,))
    l2_agent = cursor.fetchone()
    l2_agent_id = l2_agent["id"] if l2_agent else None

    reason = (
        "CRITICAL priority ticket requiring immediate Level-2 intervention"
        if priority == "CRITICAL"
        else f"Primary team '{primary_team_name}' and Backup team saturated at 8-ticket capacity."
    )

    return {
        "assigned_agent_id": l2_agent_id,
        "assigned_team_id": l2_team_id,
        "status": "ESCALATED",
        "is_escalated": 1,
        "escalation_reason": reason,
        "is_backup_assigned": 0,
        "assignment_type": "L2_ESCALATION",
        "details": f"Ticket escalated to Level-2 Specialist ({l2_agent['name'] if l2_agent else 'Unassigned'}). Reason: {reason}"
    }
