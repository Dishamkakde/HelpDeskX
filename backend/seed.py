import os
from .database import init_db, SessionLocal, engine, Base
from .models import User, Team, RoutingRule, Ticket, Assignment, StatusHistory, ValidationLog
from .auth import hash_password
from .dfa import dfa_validator
from .validation import validate_ticket_identifier
from .classification import classify_report
from .dispatch import dispatch_ticket

def seed_database():
    print("Resetting database schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    print("Creating 4 HelpDesk Teams (Capacity: 8 open tickets)...")
    teams_data = [
        {"name": "Team 1", "cap": 8},
        {"name": "Team 2", "cap": 8},
        {"name": "Team 3", "cap": 8},
        {"name": "Team 4", "cap": 8}
    ]
    team_objs = {}
    for td in teams_data:
        team = Team(
            team_name=td["name"],
            max_capacity=td["cap"],
            is_available=True,
            round_robin_pointer=0
        )
        db.add(team)
        db.flush()
        team_objs[td["name"]] = team

    print("Creating Demo Users (Admin, Staff, Handlers)...")
    users_data = [
        # Admin
        {"name": "System Administrator", "email": "admin@helpdeskx.com", "role": "ADMIN", "dept": "IT", "team": None},
        # Staff
        {"name": "Professor Alan Turing", "email": "staff@helpdeskx.com", "role": "STAFF", "dept": "CS", "team": None},
        {"name": "Dr. Grace Hopper", "email": "hopper@helpdeskx.com", "role": "STAFF", "dept": "EC", "team": None},
        # Handlers
        {"name": "Alex Rivera (Hardware Specialist)", "email": "handler1@helpdeskx.com", "role": "HANDLER", "dept": "IT", "team": team_objs["Team 1"].id},
        {"name": "Sarah Jenkins (Software Specialist)", "email": "handler2@helpdeskx.com", "role": "HANDLER", "dept": "IT", "team": team_objs["Team 2"].id},
        {"name": "Elena Rostova (Network Engineer)", "email": "handler3@helpdeskx.com", "role": "HANDLER", "dept": "IT", "team": team_objs["Team 3"].id},
        {"name": "Victor Ramos (Security Analyst)", "email": "handler4@helpdeskx.com", "role": "HANDLER", "dept": "HR", "team": team_objs["Team 4"].id},
    ]

    for ud in users_data:
        pwd = "Admin@123" if ud["role"] == "ADMIN" else ("Staff@123" if ud["role"] == "STAFF" else "Handler@123")
        u = User(
            name=ud["name"],
            email=ud["email"],
            password_hash=hash_password(pwd),
            role=ud["role"],
            department=ud["dept"],
            team_id=ud["team"],
            is_available=True
        )
        db.add(u)
    db.commit()

    print("Creating Configurable Routing Rules (BCS502)...")
    routing_rules_data = [
        ("CS", "HARDWARE", team_objs["Team 1"].id, team_objs["Team 2"].id),
        ("CS", "SOFTWARE", team_objs["Team 2"].id, team_objs["Team 1"].id),
        ("IT", "NETWORK", team_objs["Team 3"].id, team_objs["Team 4"].id),
        ("HR", "ACCESS", team_objs["Team 4"].id, team_objs["Team 2"].id),
        ("EC", "HARDWARE", team_objs["Team 1"].id, team_objs["Team 3"].id),
        ("EC", "NETWORK", team_objs["Team 3"].id, team_objs["Team 1"].id),
        ("ANY", "OTHER", team_objs["Team 4"].id, team_objs["Team 1"].id),
    ]

    for dept, cat, primary_id, backup_id in routing_rules_data:
        rr = RoutingRule(
            department_code=dept,
            category=cat,
            primary_team_id=primary_id,
            backup_team_id=backup_id,
            is_active=True
        )
        db.add(rr)
    db.commit()

    print("Submitting and Dispatching Sample Tickets...")
    sample_reports = [
        ("CS-101-H", "Laptop monitor screen flickering and keyboard unresponsive", "staff@helpdeskx.com"),
        ("CS-102-M", "Software application crash on Python compiler update", "staff@helpdeskx.com"),
        ("IT-201-H", "Corporate Wi-Fi disconnected and internet latency high", "staff@helpdeskx.com"),
        ("HR-301-L", "Employee password reset request and account login locked", "hopper@helpdeskx.com"),
        ("EC-401-M", "Computer motherboard overheating in department lab", "hopper@helpdeskx.com"),
        ("ME-501-L", "General inquiry regarding projector cable in seminar hall", "hopper@helpdeskx.com")
    ]

    for i, (ident, desc, user_email) in enumerate(sample_reports, start=1):
        val = validate_ticket_identifier(ident)
        clf = classify_report(desc)
        user = db.query(User).filter(User.email == user_email).first()

        ticket = Ticket(
            public_ticket_id=f"HDX-2026-{i:04d}",
            reporter_id=user.id,
            department_code=val["department_code"],
            issue_code=val["issue_code"],
            priority=val["priority_code"],
            ticket_identifier=ident,
            description=desc,
            category=clf["category"],
            dfa_result=val["dfa_result"],
            regex_result=val["regex_result"],
            validation_status=val["validation_status"],
            validation_reason=val["validation_reason"],
            status="Pending"
        )
        db.add(ticket)
        db.commit()

        # Execute dispatch
        dispatch_ticket(db, ticket)

    print("Database seeding completed successfully!")
    db.close()

if __name__ == "__main__":
    seed_database()

