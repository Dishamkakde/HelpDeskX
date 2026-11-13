import os
import time
import asyncio
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .database import get_db, init_db, get_db_path
from .models import (
    TicketCreate, TicketStatusUpdate, TicketReassign,
    TicketEscalate, PriorityOverride, TicketNoteCreate,
    ClassificationRequest, ConcurrentSubmissionRequest
)
from .classifiers.dfa_engine import classify_text_dfa, get_dfa_trace, dfa_instance
from .classifiers.regex_engine import classify_text_regex
from .classifiers.hybrid import classify_text_hybrid
from .services.assignment import dispatch_ticket, assignment_lock
from .services.stats import get_dashboard_statistics
from .auth import get_current_role, require_role

# Initialize DB if not already initialized
init_db()

app = FastAPI(
    title="HelpDeskX API",
    description="Automata-Powered Intelligent Helpdesk Routing & Dispatch System",
    version="1.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")

# ----------------- SYSTEM & CLASSIFIER ENDPOINTS -----------------

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "HelpDeskX",
        "version": "1.0.0",
        "database": os.path.basename(get_db_path()),
        "formal_automata": "DFA M=(Q,Sigma,delta,q0,F)",
        "timestamp": time.time()
    }

@app.post("/api/classify")
def classify_text(req: ClassificationRequest):
    """
    Test DFA, Regex, or Hybrid engines independently or side-by-side.
    """
    mode = (req.engine or "HYBRID").upper()
    if mode == "DFA":
        return classify_text_dfa(req.text)
    elif mode == "REGEX":
        return classify_text_regex(req.text)
    elif mode == "ALL":
        return {
            "dfa": classify_text_dfa(req.text),
            "regex": classify_text_regex(req.text),
            "hybrid": classify_text_hybrid(req.text)
        }
    else:
        return classify_text_hybrid(req.text)

@app.get("/api/dfa/trace")
def dfa_trace(token: str = Query(..., min_length=1, description="Single token to trace through DFA states")):
    """Step-by-step state transition trace through formal DFA graph."""
    return get_dfa_trace(token)

@app.get("/api/dfa/spec")
def dfa_formal_specification():
    """Returns the formal mathematical 5-tuple M = (Q, Sigma, delta, q0, F)."""
    return dfa_instance.get_formal_spec()

# ----------------- TICKET OPERATIONS -----------------

@app.get("/api/tickets")
def list_tickets(
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    assigned_agent_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                t.*,
                a.name as assigned_agent_name,
                tm.name as assigned_team_name
            FROM tickets t
            LEFT JOIN agents a ON t.assigned_agent_id = a.id
            LEFT JOIN teams tm ON t.assigned_team_id = tm.id
            WHERE 1=1
        """
        params = []

        if category:
            query += " AND t.category = ?"
            params.append(category.upper())
        if status_filter:
            query += " AND t.status = ?"
            params.append(status_filter.upper())
        if priority:
            query += " AND t.priority = ?"
            params.append(priority.upper())
        if assigned_agent_id:
            query += " AND t.assigned_agent_id = ?"
            params.append(assigned_agent_id)
        if search:
            query += " AND (t.title LIKE ? OR t.description LIKE ? OR t.ticket_number LIKE ? OR t.requester_name LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term])

        query += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@app.get("/api/tickets/{ticket_id}")
def get_ticket_details(ticket_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                t.*,
                a.name as assigned_agent_name,
                a.email as assigned_agent_email,
                tm.name as assigned_team_name
            FROM tickets t
            LEFT JOIN agents a ON t.assigned_agent_id = a.id
            LEFT JOIN teams tm ON t.assigned_team_id = tm.id
            WHERE t.id = ?
        """, (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket #{ticket_id} not found.")

        cursor.execute("""
            SELECT * FROM ticket_logs WHERE ticket_id = ? ORDER BY id ASC
        """, (ticket_id,))
        logs = cursor.fetchall()

        result = dict(ticket)
        result["logs"] = [dict(l) for l in logs]
        return result

@app.post("/api/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(ticket_data: TicketCreate, user_role: str = Depends(get_current_role)):
    """
    Creates ticket with automated DFA/Regex classification,
    and dispatches via Round-Robin, 8-Ticket Capacity, Backup, or L2 Escalation.
    Thread-safe / Concurrency-safe via assignment_lock and SQLite transactions.
    """
    text_content = f"{ticket_data.title} {ticket_data.description}"
    
    # 1. Classification
    category = ticket_data.category
    priority = ticket_data.priority
    classifier_used = "MANUAL"
    confidence = 1.0

    if not category:
        clf_mode = (ticket_data.preferred_classifier or "HYBRID").upper()
        if clf_mode == "DFA":
            clf_res = classify_text_dfa(text_content)
        elif clf_mode == "REGEX":
            clf_res = classify_text_regex(text_content)
        else:
            clf_res = classify_text_hybrid(text_content)

        category = clf_res["category"]
        confidence = clf_res["confidence"]
        classifier_used = clf_mode
        if not priority:
            priority = clf_res.get("suggested_priority", "MEDIUM")

    if not priority:
        priority = "MEDIUM"

    # Concurrency-safe dispatch block
    async with assignment_lock:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Dispatch
            dispatch_info = dispatch_ticket(cursor, category, priority)
            
            # Generate next ticket number
            cursor.execute("SELECT MAX(id) as max_id FROM tickets")
            max_id = cursor.fetchone()["max_id"] or 1000
            ticket_number = f"HDX-{max_id + 1}"

            cursor.execute("""
                INSERT INTO tickets (
                    ticket_number, title, description, requester_id, requester_name,
                    requester_dept, category, classifier_used, classifier_confidence,
                    priority, status, assigned_agent_id, assigned_team_id,
                    is_escalated, escalation_reason, is_backup_assigned, priority_overridden
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                ticket_number, ticket_data.title, ticket_data.description,
                ticket_data.requester_id, ticket_data.requester_name,
                ticket_data.requester_dept, category, classifier_used, confidence,
                priority, dispatch_info["status"], dispatch_info["assigned_agent_id"],
                dispatch_info["assigned_team_id"], dispatch_info["is_escalated"],
                dispatch_info["escalation_reason"], dispatch_info["is_backup_assigned"]
            ))

            ticket_id = cursor.lastrowid

            # Add creation log
            cursor.execute("""
                INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
                VALUES (?, 'CREATED', ?, ?)
            """, (ticket_id, f"Requester ({ticket_data.requester_name})", f"Ticket created. Classification: {category} via {classifier_used} (conf: {confidence})."))

            # Add dispatch log
            cursor.execute("""
                INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
                VALUES (?, ?, 'AUTO_DISPATCH', ?)
            """, (ticket_id, dispatch_info["assignment_type"], dispatch_info["details"]))

            conn.commit()

            cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            created_row = dict(cursor.fetchone())
            created_row["dispatch_info"] = dispatch_info
            return created_row

@app.patch("/api/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    role: str = Depends(require_role(["agent", "lead", "admin"]))
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_status = ticket["status"]
        new_status = payload.status.upper()
        
        resolved_sql = ", resolved_at = CURRENT_TIMESTAMP" if new_status in ("RESOLVED", "CLOSED") else ""
        
        cursor.execute(f"""
            UPDATE tickets 
            SET status = ?, updated_at = CURRENT_TIMESTAMP {resolved_sql}
            WHERE id = ?
        """, (new_status, ticket_id))

        note_details = f"Status changed from {old_status} to {new_status}."
        if payload.note:
            note_details += f" Note: {payload.note}"

        cursor.execute("""
            INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
            VALUES (?, 'STATUS_CHANGE', ?, ?)
        """, (ticket_id, f"{role.upper()}_USER", note_details))

        conn.commit()
        return {"ticket_id": ticket_id, "old_status": old_status, "new_status": new_status, "note": payload.note}

@app.post("/api/tickets/{ticket_id}/reassign")
def reassign_ticket(
    ticket_id: int,
    payload: TicketReassign,
    role: str = Depends(require_role(["lead", "admin"]))
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        cursor.execute("SELECT id, name, team_id FROM agents WHERE id = ?", (payload.agent_id,))
        new_agent = cursor.fetchone()
        if not new_agent:
            raise HTTPException(status_code=404, detail="Target agent not found")

        cursor.execute("""
            UPDATE tickets
            SET assigned_agent_id = ?, assigned_team_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_agent["id"], new_agent["team_id"], ticket_id))

        cursor.execute("""
            INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
            VALUES (?, 'REASSIGNED', ?, ?)
        """, (ticket_id, f"{role.upper()}_USER", f"Ticket reassigned to {new_agent['name']}. Reason: {payload.reason}"))

        conn.commit()
        return {"ticket_id": ticket_id, "new_agent_id": new_agent["id"], "new_agent_name": new_agent["name"]}

@app.post("/api/tickets/{ticket_id}/escalate")
def escalate_ticket(
    ticket_id: int,
    payload: TicketEscalate,
    role: str = Depends(require_role(["agent", "lead", "admin"]))
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        cursor.execute("SELECT id, name FROM teams WHERE name = 'Level-2 Escalations'")
        l2_team = cursor.fetchone()
        l2_team_id = l2_team["id"] if l2_team else ticket["assigned_team_id"]

        cursor.execute("SELECT id, name FROM agents WHERE team_id = ? AND is_active = 1 LIMIT 1", (l2_team_id,))
        l2_agent = cursor.fetchone()
        l2_agent_id = l2_agent["id"] if l2_agent else None

        cursor.execute("""
            UPDATE tickets
            SET status = 'ESCALATED', is_escalated = 1, escalation_reason = ?,
                assigned_team_id = ?, assigned_agent_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (payload.reason, l2_team_id, l2_agent_id, ticket_id))

        cursor.execute("""
            INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
            VALUES (?, 'ESCALATED', ?, ?)
        """, (ticket_id, f"{role.upper()}_USER", f"Manually escalated to Level-2. Reason: {payload.reason}"))

        conn.commit()
        return {
            "ticket_id": ticket_id,
            "status": "ESCALATED",
            "assigned_team": "Level-2 Escalations",
            "assigned_agent": l2_agent["name"] if l2_agent else "Unassigned",
            "reason": payload.reason
        }

@app.post("/api/tickets/{ticket_id}/override-priority")
def override_ticket_priority(
    ticket_id: int,
    payload: PriorityOverride,
    role: str = Depends(require_role(["lead", "admin"]))
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_prio = ticket["priority"]
        cursor.execute("""
            UPDATE tickets
            SET priority = ?, priority_overridden = 1, override_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (payload.new_priority, payload.reason, ticket_id))

        cursor.execute("""
            INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
            VALUES (?, 'PRIORITY_OVERRIDE', ?, ?)
        """, (ticket_id, f"{role.upper()}_USER", f"Priority overridden from {old_prio} to {payload.new_priority}. Reason: {payload.reason}"))

        conn.commit()
        return {
            "ticket_id": ticket_id,
            "old_priority": old_prio,
            "new_priority": payload.new_priority,
            "reason": payload.reason
        }

@app.post("/api/tickets/{ticket_id}/notes")
def add_ticket_note(
    ticket_id: int,
    payload: TicketNoteCreate,
    role: str = Depends(require_role(["agent", "lead", "admin"]))
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Ticket not found")

        cursor.execute("""
            INSERT INTO ticket_logs (ticket_id, action, performed_by, details)
            VALUES (?, 'NOTE_ADDED', ?, ?)
        """, (ticket_id, f"{role.upper()}_USER", payload.note))

        conn.commit()
        return {"ticket_id": ticket_id, "status": "note_added", "note": payload.note}

# ----------------- TEAMS & AGENTS -----------------

@app.get("/api/teams")
def list_teams_and_agents():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams ORDER BY id ASC")
        teams = [dict(t) for t in cursor.fetchall()]

        cursor.execute("""
            SELECT 
                a.*,
                COUNT(tk.id) as active_tickets
            FROM agents a
            LEFT JOIN tickets tk ON a.id = tk.assigned_agent_id 
                AND tk.status IN ('OPEN', 'IN_PROGRESS', 'ESCALATED')
            GROUP BY a.id
            ORDER BY a.id ASC
        """)
        agents = [dict(a) for a in cursor.fetchall()]

        team_dict = {t["id"]: {**t, "agents": []} for t in teams}
        for a in agents:
            tid = a["team_id"]
            if tid in team_dict:
                team_dict[tid]["agents"].append(a)

        return list(team_dict.values())

# ----------------- DASHBOARD ANALYTICS -----------------

@app.get("/api/dashboard/stats")
def dashboard_stats():
    """Returns real SQLite analytics for all dashboard components."""
    return get_dashboard_statistics()

# ----------------- SIMULATION & STRESS TEST -----------------

@app.post("/api/simulate/concurrent-submissions")
async def simulate_concurrent_submissions(req: ConcurrentSubmissionRequest):
    """
    Submits multiple tickets concurrently using asyncio.gather to test
    round-robin rotation, 8-ticket capacity overflow, and database lock handling.
    """
    count = req.count
    test_titles = [
        "Network latency spike on main gateway",
        "Monitor flickering with black screen",
        "Application memory leak causing crash",
        "Password expired unable to login to portal",
        "Invoice mismatch on annual SaaS contract",
        "Laptop charger port overheating severely",
        "Wi-Fi disconnects every 5 minutes",
        "Unhandled exception in production service",
        "Request for elevated sudo admin access",
        "Double billing charge on credit card statement"
    ]

    async def submit_one(i: int):
        title = test_titles[i % len(test_titles)]
        prio = req.priority or ("CRITICAL" if i % 5 == 0 else "MEDIUM")
        item = TicketCreate(
            title=f"[Simulated Batch] {title} #{i+1}",
            description=f"Automated concurrency simulation test dispatch ticket #{i+1} verifying SQLite transactions.",
            requester_id=f"EMP-SIM-{i+1:03d}",
            requester_name=f"SimUser {i+1}",
            requester_dept="QA Stress Testing",
            category=req.category,
            priority=prio,
            preferred_classifier="HYBRID"
        )
        return await create_ticket(item, user_role="admin")

    start = time.perf_counter()
    tasks = [submit_one(i) for i in range(count)]
    results = await asyncio.gather(*tasks)
    elapsed = round((time.perf_counter() - start) * 1000, 2)

    return {
        "dispatched_count": len(results),
        "total_time_ms": elapsed,
        "avg_time_per_ticket_ms": round(elapsed / len(results), 2),
        "tickets": [
            {
                "id": t["id"],
                "ticket_number": t["ticket_number"],
                "category": t["category"],
                "priority": t["priority"],
                "status": t["status"],
                "assigned_agent_id": t["assigned_agent_id"],
                "assignment_type": t.get("dispatch_info", {}).get("assignment_type", "UNKNOWN")
            }
            for t in results
        ]
    }

@app.post("/api/system/reset-demo")
def reset_demo_database(role: str = Depends(require_role(["admin"]))):
    from ...seed_data import seed_database
    seed_database(reset=True)
    return {"status": "success", "message": "Demo database successfully re-seeded."}

# ----------------- STATIC ASSETS & SPA ROUTING -----------------

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Frontend index.html not found"}
