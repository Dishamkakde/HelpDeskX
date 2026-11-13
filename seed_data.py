import os
import sqlite3
from backend.app.database import init_db, get_db, get_db_path

TEAMS_DATA = [
    ("Hardware Support", "HARDWARE", 8),
    ("Software Engineering", "SOFTWARE", 8),
    ("Network Operations", "NETWORK", 8),
    ("Security & Access", "ACCESS_SECURITY", 8),
    ("Billing & Finance", "BILLING_ACCOUNT", 8),
    ("General Backup", "BACKUP", 8),
    ("Level-2 Escalations", "ESCALATION", 16)
]

AGENTS_DATA = [
    # Hardware
    ("Alex Rivera", "alex.rivera@helpdeskx.com", "Hardware Support", "agent", 8),
    ("Liam Chen", "liam.chen@helpdeskx.com", "Hardware Support", "agent", 8),
    # Software
    ("Sarah Jenkins", "sarah.jenkins@helpdeskx.com", "Software Engineering", "agent", 8),
    ("Marcus Brody", "marcus.brody@helpdeskx.com", "Software Engineering", "agent", 8),
    # Network
    ("Elena Rostova", "elena.rostova@helpdeskx.com", "Network Operations", "agent", 8),
    ("David Kim", "david.kim@helpdeskx.com", "Network Operations", "agent", 8),
    # Security
    ("Rachel Vance", "rachel.vance@helpdeskx.com", "Security & Access", "agent", 8),
    ("Omar Farooq", "omar.farooq@helpdeskx.com", "Security & Access", "agent", 8),
    # Billing
    ("Chloe Bennett", "chloe.bennett@helpdeskx.com", "Billing & Finance", "agent", 8),
    ("Victor Ramos", "victor.ramos@helpdeskx.com", "Billing & Finance", "agent", 8),
    # Backup & L2
    ("Jordan Taylor", "jordan.taylor@helpdeskx.com", "General Backup", "backup_agent", 8),
    ("Dr. Evelyn Reed", "evelyn.reed@helpdeskx.com", "Level-2 Escalations", "l2_specialist", 16)
]

SAMPLE_TICKETS = [
    {
        "title": "Dual monitor display flickering with HDMI cable",
        "desc": "My second monitor randomly flickers and goes black when connected via HDMI to laptop dock.",
        "emp_id": "EMP-102", "name": "Alice Walker", "dept": "Product",
        "category": "HARDWARE", "priority": "MEDIUM", "agent": "Alex Rivera", "team": "Hardware Support", "status": "IN_PROGRESS"
    },
    {
        "title": "Application crash on startup after Windows 11 update",
        "desc": "Uncaught fatal runtime exception crash in python and compiler toolchain following OS patch.",
        "emp_id": "EMP-205", "name": "Bob Martin", "dept": "Engineering",
        "category": "SOFTWARE", "priority": "HIGH", "agent": "Sarah Jenkins", "team": "Software Engineering", "status": "OPEN"
    },
    {
        "title": "VPN connection drops every 10 minutes over Wi-Fi",
        "desc": "Unable to stay connected to corporate OpenVPN. Frequent packet loss and DNS resolve timeouts.",
        "emp_id": "EMP-312", "name": "Clara Oswald", "dept": "Operations",
        "category": "NETWORK", "priority": "HIGH", "agent": "Elena Rostova", "team": "Network Operations", "status": "IN_PROGRESS"
    },
    {
        "title": "Password reset and 2FA authenticator desynchronization",
        "desc": "Account locked out after expired credentials. Need immediate MFA token reset for login.",
        "emp_id": "EMP-418", "name": "Daniel Craig", "dept": "Finance",
        "category": "ACCESS_SECURITY", "priority": "CRITICAL", "agent": "Dr. Evelyn Reed", "team": "Level-2 Escalations", "status": "ESCALATED",
        "is_escalated": 1, "reason": "CRITICAL priority ticket requiring immediate Level-2 intervention"
    },
    {
        "title": "Duplicate charge on quarterly SaaS software license invoice",
        "desc": "Accounts department identified double debit payment charge for recurring enterprise subscription billing.",
        "emp_id": "EMP-529", "name": "Eva Green", "dept": "Human Resources",
        "category": "BILLING_ACCOUNT", "priority": "MEDIUM", "agent": "Chloe Bennett", "team": "Billing & Finance", "status": "RESOLVED"
    }
]

def seed_database(reset: bool = True):
    if reset and os.path.exists(get_db_path()):
        os.remove(get_db_path())
    
    init_db()

    with get_db() as conn:
        cursor = conn.cursor()

        # Insert Teams
        for name, category, cap in TEAMS_DATA:
            cursor.execute("""
                INSERT OR IGNORE INTO teams (name, category, max_capacity, current_rr_index)
                VALUES (?, ?, ?, 0)
            """, (name, category, cap))

        # Query Team IDs
        cursor.execute("SELECT id, name FROM teams")
        team_id_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Insert Agents
        for name, email, team_name, role, max_cap in AGENTS_DATA:
            team_id = team_id_map[team_name]
            cursor.execute("""
                INSERT OR IGNORE INTO agents (name, email, team_id, role, is_active, max_active_tickets)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (name, email, team_id, role, max_cap))

        # Query Agent IDs
        cursor.execute("SELECT id, name FROM agents")
        agent_id_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Insert Sample Tickets
        for i, t in enumerate(SAMPLE_TICKETS, start=1001):
            ticket_number = f"HDX-{i}"
            team_id = team_id_map.get(t["team"])
            agent_id = agent_id_map.get(t["agent"])
            is_esc = t.get("is_escalated", 0)
            reason = t.get("reason", None)
            
            cursor.execute("""
                INSERT OR IGNORE INTO tickets (
                    ticket_number, title, description, requester_id, requester_name,
                    requester_dept, category, classifier_used, classifier_confidence,
                    priority, status, assigned_agent_id, assigned_team_id,
                    is_escalated, escalation_reason, is_backup_assigned, priority_overridden
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'HYBRID', 0.95, ?, ?, ?, ?, ?, ?, 0, 0)
            """, (
                ticket_number, t["title"], t["desc"], t["emp_id"], t["name"],
                t["dept"], t["category"], t["priority"], t["status"],
                agent_id, team_id, is_esc, reason
            ))

            ticket_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
                VALUES (?, 'CREATED', 'SYSTEM_SEED', 'Initial system seed ticket created and assigned.')
            """, (ticket_id,))

        conn.commit()

    print(f"Seed complete. SQLite database initialized at {get_db_path()}")

if __name__ == "__main__":
    seed_database(reset=True)
