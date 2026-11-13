import os
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS

from .config import Config
from .database import engine, SessionLocal, init_db, Base
from .models import User, Team, Ticket, RoutingRule, Assignment, StatusHistory, Escalation, ValidationLog
from .auth import hash_password, verify_password, generate_token, login_required, roles_required
from .dfa import dfa_validator
from .validation import validate_ticket_identifier
from .classification import classify_report
from .routing import find_routing_rule, get_team_active_ticket_count, get_handler_active_ticket_count
from .dispatch import dispatch_ticket
from .analytics import get_analytics_metrics
from .escalation import get_all_escalations, resolve_escalation

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR)
app.config.from_object(Config)

# Enable CORS for cross-origin requests
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Database teardown hook
@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()

# ----------------- HEALTH & SYSTEM -----------------

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "system": "HelpDeskX — Intelligent IT Helpdesk Ticket Router",
        "bcs503_automata": "DFA M = (Q, Sigma, delta, q0, F) [Active]",
        "bcs502_networking": "Round-Robin & 8-Ticket Capacity Routing [Active]",
        "database": "SQLite + SQLAlchemy ORM",
        "timestamp": datetime.utcnow().isoformat()
    })

# ----------------- AUTHENTICATION -----------------

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(user)
    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_dict()
    })

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role = data.get("role", "STAFF").strip().upper()
    department = data.get("department", "CS").strip().upper()

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    db = SessionLocal()
    if db.query(User).filter(User.email == email).first():
        return jsonify({"error": "User with this email already exists"}), 409

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        department=department
    )
    db.add(user)
    db.commit()

    token = generate_token(user)
    return jsonify({
        "message": "User registered successfully",
        "token": token,
        "user": user.to_dict()
    }), 201

@app.route("/api/auth/me", methods=["GET"])
@login_required
def get_current_user():
    db = SessionLocal()
    user = db.query(User).filter(User.id == g.current_user["uid"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict())

# ----------------- VALIDATION (BCS503) -----------------

@app.route("/api/validate", methods=["POST"])
def validate_identifier():
    """
    Validates ticket identifier using both DFA and Regex independently.
    Format: [A-Z]{2}-[0-9]{3}-[HML] (e.g. CS-101-H)
    """
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()
    result = validate_ticket_identifier(identifier)
    return jsonify(result)

@app.route("/api/dfa/spec", methods=["GET"])
def get_dfa_specification():
    """Returns mathematical 5-tuple specification of the DFA for BCS503."""
    return jsonify(dfa_validator.get_formal_definition())

# ----------------- CLASSIFICATION (5 CATEGORIES) -----------------

@app.route("/api/classify", methods=["POST"])
def classify_text():
    """
    Classifies problem description into exactly one of 5 categories:
    ACCESS, NETWORK, HARDWARE, SOFTWARE, OTHER.
    Applies priority: ACCESS -> NETWORK -> HARDWARE -> SOFTWARE -> OTHER.
    """
    data = request.get_json() or {}
    description = data.get("description", "").strip()
    result = classify_report(description)
    return jsonify(result)

# ----------------- TICKETS -----------------

@app.route("/api/tickets", methods=["POST"])
@login_required
def submit_ticket():
    data = request.get_json() or {}
    reporter_name = data.get("reporter_name", "").strip()
    email = data.get("email", "").strip().lower()
    department = data.get("department", "CS").strip().upper()
    identifier = data.get("ticket_identifier", "").strip().upper()
    description = data.get("description", "").strip()
    issue_code_input = data.get("issue_code", "")

    if not description or not identifier:
        return jsonify({"error": "Ticket identifier and description are required"}), 400

    # 1. Automata Validation (DFA + Regex)
    val_result = validate_ticket_identifier(identifier)
    
    db = SessionLocal()

    # Log validation attempt
    v_log = ValidationLog(
        dfa_result=val_result["dfa_result"],
        regex_result=val_result["regex_result"],
        validation_result=val_result["validation_status"],
        reason=val_result["validation_reason"]
    )
    db.add(v_log)

    if not val_result["is_valid"]:
        db.commit()
        return jsonify({
            "error": "Ticket identifier rejected by automata validator",
            "validation_details": val_result
        }), 422

    # 2. Five-Category Classification (Deterministic)
    clf_result = classify_report(description)
    detected_category = clf_result["category"]

    # Priority from identifier: H, M, L
    prio_code = val_result["priority_code"] or "M"
    dept_code = val_result["department_code"] or department
    issue_code = val_result["issue_code"] or (issue_code_input or "101")

    # Generate public ticket ID: e.g. HDX-2026-001
    count = db.query(Ticket).count()
    public_id = f"HDX-2026-{count + 1:04d}"

    # Get or create reporter user
    reporter_user = db.query(User).filter(User.email == email).first()
    if not reporter_user:
        reporter_user = User(
            name=reporter_name or "Anonymous Staff",
            email=email or f"user{count+1}@helpdeskx.com",
            password_hash=hash_password("Staff@123"),
            role="STAFF",
            department=dept_code
        )
        db.add(reporter_user)
        db.flush()

    ticket = Ticket(
        public_ticket_id=public_id,
        reporter_id=reporter_user.id,
        department_code=dept_code,
        issue_code=issue_code,
        priority=prio_code,
        ticket_identifier=identifier,
        description=description,
        category=detected_category,
        dfa_result=val_result["dfa_result"],
        regex_result=val_result["regex_result"],
        validation_status=val_result["validation_status"],
        validation_reason=val_result["validation_reason"],
        status="Pending"
    )
    db.add(ticket)
    db.flush()

    # Link validation log
    v_log.ticket_id = ticket.id

    # Initial Status History
    h1 = StatusHistory(
        ticket_id=ticket.id,
        previous_status="None",
        new_status="Pending",
        changed_by=reporter_user.name,
        notes=f"Report submitted and validated by DFA+Regex. Classified as {detected_category}."
    )
    db.add(h1)
    db.commit()

    # 3. Intelligent Computer Networks Dispatch
    dispatch_result = dispatch_ticket(db, ticket)

    return jsonify({
        "message": "Ticket submitted and dispatched successfully",
        "ticket": ticket.to_dict(),
        "validation": val_result,
        "classification": clf_result,
        "dispatch": dispatch_result
    }), 201

@app.route("/api/tickets", methods=["GET"])
@login_required
def list_tickets():
    db = SessionLocal()
    query = db.query(Ticket)

    # Role-based filtering
    user_role = g.current_user.get("role", "STAFF").upper()
    user_id = g.current_user.get("uid")

    if user_role == "STAFF":
        query = query.filter(Ticket.reporter_id == user_id)
    elif user_role == "HANDLER":
        query = query.filter(Ticket.assigned_handler_id == user_id)

    # Filter parameters
    status_filter = request.args.get("status")
    category_filter = request.args.get("category")
    priority_filter = request.args.get("priority")
    search = request.args.get("search")

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if category_filter:
        query = query.filter(Ticket.category == category_filter.upper())
    if priority_filter:
        query = query.filter(Ticket.priority == priority_filter.upper())
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Ticket.public_ticket_id.like(search_pattern)) |
            (Ticket.ticket_identifier.like(search_pattern)) |
            (Ticket.description.like(search_pattern))
        )

    # Deterministic priority ordering: High -> Medium -> Low -> earlier timestamp
    tickets = query.order_by(
        Ticket.priority.asc(),  # H < M < L alphabetically!
        Ticket.created_at.asc(),
        Ticket.id.asc()
    ).all()

    return jsonify([t.to_dict() for t in tickets])

@app.route("/api/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def get_ticket(ticket_id):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    history = [h.to_dict() for h in ticket.status_history]
    assignments = [a.to_dict() for a in ticket.assignments]
    escalations = [e.to_dict() for e in ticket.escalations]

    data = ticket.to_dict()
    data["history"] = history
    data["assignments"] = assignments
    data["escalations"] = escalations
    return jsonify(data)

@app.route("/api/tickets/track/<public_ticket_id>", methods=["GET"])
def track_ticket_public(public_ticket_id):
    """Public tracking endpoint by public ticket ID (e.g. HDX-2026-0001 or CS-101-H)."""
    db = SessionLocal()
    ticket = db.query(Ticket).filter(
        (Ticket.public_ticket_id == public_ticket_id) |
        (Ticket.ticket_identifier == public_ticket_id)
    ).first()

    if not ticket:
        return jsonify({"error": "No ticket found with this identifier"}), 404

    # Build timeline: Submitted -> Validated -> Assigned -> In Progress -> Resolved
    timeline = [
        {"step": "Submitted", "timestamp": ticket.created_at.isoformat() if ticket.created_at else None, "completed": True},
        {"step": "Validated (DFA+Regex)", "timestamp": ticket.created_at.isoformat() if ticket.created_at else None, "completed": ticket.validation_status == "PASSED"},
        {"step": "Assigned", "timestamp": ticket.created_at.isoformat() if ticket.created_at else None, "completed": ticket.status in ("Assigned", "In Progress", "Resolved")},
        {"step": "In Progress", "timestamp": ticket.updated_at.isoformat() if ticket.status in ("In Progress", "Resolved") else None, "completed": ticket.status in ("In Progress", "Resolved")},
        {"step": "Resolved", "timestamp": ticket.updated_at.isoformat() if ticket.status == "Resolved" else None, "completed": ticket.status == "Resolved"}
    ]

    result = ticket.to_dict()
    result["timeline"] = timeline
    result["status_history"] = [h.to_dict() for h in ticket.status_history]
    return jsonify(result)

@app.route("/api/tickets/<int:ticket_id>/status", methods=["PATCH"])
@login_required
def update_ticket_status(ticket_id):
    """
    Valid transitions:
    Pending -> Assigned
    Assigned -> In Progress
    In Progress -> Resolved
    """
    data = request.get_json() or {}
    new_status = data.get("status", "").strip()
    notes = data.get("notes", "").strip()

    valid_statuses = ["Pending", "Assigned", "In Progress", "Resolved"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Allowed: {valid_statuses}"}), 400

    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    # Authorization: Handlers can only update tickets assigned to them
    user_role = g.current_user.get("role", "STAFF").upper()
    user_id = g.current_user.get("uid")

    if user_role == "HANDLER" and ticket.assigned_handler_id != user_id:
        return jsonify({"error": "Handlers can only update tickets assigned to them"}), 403

    prev_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = datetime.utcnow()

    history = StatusHistory(
        ticket_id=ticket.id,
        previous_status=prev_status,
        new_status=new_status,
        changed_by=g.current_user.get("name", "User"),
        notes=notes or f"Status changed from {prev_status} to {new_status}."
    )
    db.add(history)
    db.commit()

    return jsonify({
        "message": "Status updated successfully",
        "ticket": ticket.to_dict()
    })

@app.route("/api/tickets/<int:ticket_id>/override-priority", methods=["POST"])
@login_required
@roles_required("ADMIN")
def override_priority(ticket_id):
    """Emergency priority override mechanism controlled by Admin."""
    data = request.get_json() or {}
    new_priority = data.get("priority", "").strip().upper()
    reason = data.get("reason", "").strip()

    if new_priority not in ("H", "M", "L"):
        return jsonify({"error": "Priority must be H, M, or L"}), 400
    if not reason:
        return jsonify({"error": "Justification reason is required for priority override"}), 400

    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    old_prio = ticket.priority
    ticket.priority = new_priority

    history = StatusHistory(
        ticket_id=ticket.id,
        previous_status=ticket.status,
        new_status=ticket.status,
        changed_by=f"ADMIN_OVERRIDE ({g.current_user.get('name')})",
        notes=f"Emergency Priority Override: {old_prio} -> {new_priority}. Reason: {reason}"
    )
    db.add(history)
    db.commit()

    return jsonify({
        "message": "Priority successfully overridden",
        "ticket_id": ticket.id,
        "old_priority": old_prio,
        "new_priority": new_priority,
        "reason": reason
    })

# ----------------- ROUTING & NETWORKING (BCS502) -----------------

@app.route("/api/routing", methods=["GET"])
@login_required
def get_routing_rules():
    db = SessionLocal()
    rules = db.query(RoutingRule).all()
    return jsonify([r.to_dict() for r in rules])

@app.route("/api/routing", methods=["POST"])
@login_required
@roles_required("ADMIN")
def create_routing_rule():
    data = request.get_json() or {}
    dept = data.get("department_code", "").strip().upper()
    cat = data.get("category", "").strip().upper()
    primary_id = data.get("primary_team_id")
    backup_id = data.get("backup_team_id")

    if not dept or not cat or not primary_id or not backup_id:
        return jsonify({"error": "Department code, category, primary team, and backup team are required"}), 400

    db = SessionLocal()
    rule = RoutingRule(
        department_code=dept,
        category=cat,
        primary_team_id=primary_id,
        backup_team_id=backup_id,
        is_active=True
    )
    db.add(rule)
    db.commit()
    return jsonify(rule.to_dict()), 201

@app.route("/api/routing/<int:rule_id>", methods=["PATCH"])
@login_required
@roles_required("ADMIN")
def update_routing_rule(rule_id):
    data = request.get_json() or {}
    db = SessionLocal()
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        return jsonify({"error": "Routing rule not found"}), 404

    if "primary_team_id" in data:
        rule.primary_team_id = data["primary_team_id"]
    if "backup_team_id" in data:
        rule.backup_team_id = data["backup_team_id"]
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])

    db.commit()
    return jsonify(rule.to_dict())

@app.route("/api/dispatch/<int:ticket_id>", methods=["POST"])
@login_required
@roles_required("ADMIN")
def manual_dispatch(ticket_id):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    res = dispatch_ticket(db, ticket)
    return jsonify(res)

# ----------------- TEAMS & 8-CAPACITY -----------------

@app.route("/api/teams", methods=["GET"])
@login_required
def get_teams():
    db = SessionLocal()
    teams = db.query(Team).order_by(Team.id.asc()).all()
    results = []
    for t in teams:
        active_count = get_team_active_ticket_count(db, t.id)
        results.append(t.to_dict(active_count=active_count))
    return jsonify(results)

@app.route("/api/teams/<int:team_id>", methods=["PATCH"])
@login_required
@roles_required("ADMIN")
def update_team(team_id):
    data = request.get_json() or {}
    db = SessionLocal()
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    if "is_available" in data:
        team.is_available = bool(data["is_available"])
    if "max_capacity" in data:
        team.max_capacity = int(data["max_capacity"])

    db.commit()
    active = get_team_active_ticket_count(db, team.id)
    return jsonify(team.to_dict(active_count=active))

# ----------------- HANDLERS -----------------

@app.route("/api/handlers", methods=["GET"])
@login_required
def get_handlers():
    db = SessionLocal()
    handlers = db.query(User).filter(User.role == "HANDLER").all()
    results = []
    for h in handlers:
        data = h.to_dict()
        data["active_tickets"] = get_handler_active_ticket_count(db, h.id)
        results.append(data)
    return jsonify(results)

@app.route("/api/handlers/<int:handler_id>/availability", methods=["PATCH"])
@login_required
def set_handler_availability(handler_id):
    db = SessionLocal()
    handler = db.query(User).filter(User.id == handler_id, User.role == "HANDLER").first()
    if not handler:
        return jsonify({"error": "Handler not found"}), 404

    # Handlers can update themselves, Admins can update any handler
    user_role = g.current_user.get("role", "").upper()
    user_id = g.current_user.get("uid")

    if user_role == "HANDLER" and handler.id != user_id:
        return jsonify({"error": "Handlers can only modify their own availability"}), 403

    data = request.get_json() or {}
    if "is_available" in data:
        handler.is_available = bool(data["is_available"])
        db.commit()

    return jsonify(handler.to_dict())

# ----------------- ANALYTICS & ESCALATIONS -----------------

@app.route("/api/analytics", methods=["GET"])
@login_required
def get_analytics():
    db = SessionLocal()
    metrics = get_analytics_metrics(db)
    return jsonify(metrics)

@app.route("/api/escalations", methods=["GET"])
@login_required
def get_escalations_list():
    db = SessionLocal()
    res = get_all_escalations(db)
    return jsonify(res)

@app.route("/api/escalations/<int:escalation_id>/resolve", methods=["POST"])
@login_required
@roles_required("ADMIN")
def resolve_l2_escalation(escalation_id):
    data = request.get_json() or {}
    action = data.get("action", "RESOLVE")
    target_team = data.get("target_team_id")
    target_handler = data.get("target_handler_id")
    notes = data.get("notes")

    db = SessionLocal()
    try:
        res = resolve_escalation(db, escalation_id, action, target_team, target_handler, notes)
        return jsonify(res)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

# ----------------- CONCURRENCY STRESS SIMULATOR -----------------

@app.route("/api/simulate/concurrent-submissions", methods=["POST"])
@login_required
@roles_required("ADMIN")
def simulate_concurrent_batch():
    """Simulates simultaneous submissions to stress-test 8-ticket capacity and round-robin."""
    data = request.get_json() or {}
    batch_size = min(int(data.get("count", 10)), 30)

    test_samples = [
        ("CS-101-H", "Laptop monitor won't turn on and screen is flickering"),
        ("CS-102-M", "Crash bug when running compiler and IDE update"),
        ("IT-201-H", "Corporate Wi-Fi disconnected and latency is high"),
        ("HR-301-L", "Cannot login with expired password need access reset"),
        ("EC-401-M", "Motherboard overheating and computer fan noisy"),
        ("CS-105-H", "Application fatal error and corrupted software package"),
        ("IT-205-M", "OpenVPN tunnel failure and network connection dropped"),
        ("HR-305-H", "Account lockout unable to access HR portal"),
        ("EC-405-L", "Need assistance with lab computer hardware mouse"),
        ("ME-501-M", "Printer paper jam in department office")
    ]

    results = []
    start_time = time.perf_counter()

    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == "ADMIN").first()

    for i in range(batch_size):
        ident, desc = test_samples[i % len(test_samples)]
        val = validate_ticket_identifier(ident)
        clf = classify_report(desc)

        ticket = Ticket(
            public_ticket_id=f"HDX-SIM-{db.query(Ticket).count() + 1:04d}",
            reporter_id=admin_user.id if admin_user else 1,
            department_code=val["department_code"] or "CS",
            issue_code=val["issue_code"] or "101",
            priority=val["priority_code"] or "M",
            ticket_identifier=ident,
            description=f"[Simulated Batch #{i+1}] {desc}",
            category=clf["category"],
            dfa_result=val["dfa_result"],
            regex_result=val["regex_result"],
            validation_status=val["validation_status"],
            status="Pending"
        )
        db.add(ticket)
        db.commit()

        dispatch_res = dispatch_ticket(db, ticket)
        results.append({
            "ticket_id": ticket.id,
            "public_id": ticket.public_ticket_id,
            "identifier": ticket.ticket_identifier,
            "category": ticket.category,
            "priority": ticket.priority,
            "dispatch": dispatch_res
        })

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return jsonify({
        "dispatched_count": len(results),
        "total_time_ms": elapsed_ms,
        "results": results
    })

# ----------------- STATIC FRONTEND SERVING -----------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)

