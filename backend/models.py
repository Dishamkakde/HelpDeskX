from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="STAFF")  # ADMIN, STAFF, HANDLER
    department = Column(String(50), nullable=True)  # CS, IT, HR, EC, ME, EE
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team", back_populates="handlers")
    tickets_reported = relationship("Ticket", foreign_keys="Ticket.reporter_id", back_populates="reporter")
    tickets_assigned = relationship("Ticket", foreign_keys="Ticket.assigned_handler_id", back_populates="handler")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "department": self.department,
            "team_id": self.team_id,
            "team_name": self.team.team_name if self.team else None,
            "is_available": self.is_available,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), unique=True, nullable=False)
    max_capacity = Column(Integer, default=8, nullable=False)  # Exactly 8 OPEN tickets
    is_available = Column(Boolean, default=True, nullable=False)
    round_robin_pointer = Column(Integer, default=0, nullable=False)

    handlers = relationship("User", back_populates="team")
    tickets = relationship("Ticket", back_populates="assigned_team")

    def to_dict(self, active_count=0):
        return {
            "id": self.id,
            "team_name": self.team_name,
            "max_capacity": self.max_capacity,
            "is_available": self.is_available,
            "round_robin_pointer": self.round_robin_pointer,
            "active_tickets_count": active_count,
            "remaining_capacity": max(0, self.max_capacity - active_count),
            "is_at_capacity": active_count >= self.max_capacity,
            "handlers_count": len(self.handlers)
        }

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_ticket_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g. HDX-2026-001
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_code = Column(String(10), nullable=False)  # e.g. CS, IT, HR
    issue_code = Column(String(10), nullable=False)       # e.g. 101, 205
    priority = Column(String(5), nullable=False)          # H, M, L
    ticket_identifier = Column(String(20), nullable=False) # e.g. CS-101-H
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)         # HARDWARE, SOFTWARE, NETWORK, ACCESS, OTHER
    
    dfa_result = Column(String(20), nullable=False)       # VALID / INVALID
    regex_result = Column(String(20), nullable=False)     # VALID / INVALID
    validation_status = Column(String(20), nullable=False)# PASSED / REJECTED
    validation_reason = Column(Text, nullable=True)

    status = Column(String(30), default="Pending", nullable=False)  # Pending, Assigned, In Progress, Resolved
    assigned_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    assigned_handler_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    is_escalated = Column(Boolean, default=False)
    is_backup = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="tickets_reported")
    handler = relationship("User", foreign_keys=[assigned_handler_id], back_populates="tickets_assigned")
    assigned_team = relationship("Team", back_populates="tickets")
    
    assignments = relationship("Assignment", back_populates="ticket", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="ticket", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="ticket", cascade="all, delete-orphan")
    validation_logs = relationship("ValidationLog", back_populates="ticket", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "public_ticket_id": self.public_ticket_id,
            "ticket_identifier": self.ticket_identifier,
            "reporter_id": self.reporter_id,
            "reporter_name": self.reporter.name if self.reporter else None,
            "reporter_email": self.reporter.email if self.reporter else None,
            "department_code": self.department_code,
            "issue_code": self.issue_code,
            "priority": self.priority,
            "description": self.description,
            "category": self.category,
            "dfa_result": self.dfa_result,
            "regex_result": self.regex_result,
            "validation_status": self.validation_status,
            "validation_reason": self.validation_reason,
            "status": self.status,
            "assigned_team_id": self.assigned_team_id,
            "assigned_team_name": self.assigned_team.team_name if self.assigned_team else None,
            "assigned_handler_id": self.assigned_handler_id,
            "assigned_handler_name": self.handler.name if self.handler else None,
            "is_escalated": self.is_escalated,
            "is_backup": self.is_backup,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department_code = Column(String(10), nullable=False)  # CS, IT, HR, EC, ANY
    category = Column(String(50), nullable=False)         # HARDWARE, SOFTWARE, NETWORK, ACCESS, OTHER
    primary_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    backup_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    primary_team = relationship("Team", foreign_keys=[primary_team_id])
    backup_team = relationship("Team", foreign_keys=[backup_team_id])

    def to_dict(self):
        return {
            "id": self.id,
            "department_code": self.department_code,
            "category": self.category,
            "primary_team_id": self.primary_team_id,
            "primary_team_name": self.primary_team.team_name if self.primary_team else None,
            "backup_team_id": self.backup_team_id,
            "backup_team_name": self.backup_team.team_name if self.backup_team else None,
            "is_active": self.is_active
        }

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    handler_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assignment_type = Column(String(50), nullable=False)  # PRIMARY, BACKUP, LEVEL_2, MANUAL
    assignment_reason = Column(Text, nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="assignments")
    team = relationship("Team")
    handler = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "team_id": self.team_id,
            "team_name": self.team.team_name if self.team else None,
            "handler_id": self.handler_id,
            "handler_name": self.handler.name if self.handler else None,
            "assignment_type": self.assignment_type,
            "assignment_reason": self.assignment_reason,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None
        }

class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    previous_status = Column(String(30), nullable=False)
    new_status = Column(String(30), nullable=False)
    changed_by = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    ticket = relationship("Ticket", back_populates="status_history")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "changed_by": self.changed_by,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "notes": self.notes
        }

class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    escalation_level = Column(String(20), default="Level-2", nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(30), default="Pending L2 Review", nullable=False)

    ticket = relationship("Ticket", back_populates="escalations")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "ticket_public_id": self.ticket.public_ticket_id if self.ticket else None,
            "escalation_level": self.escalation_level,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status
        }

class ValidationLog(Base):
    __tablename__ = "validation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    dfa_result = Column(String(20), nullable=False)
    regex_result = Column(String(20), nullable=False)
    validation_result = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="validation_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "dfa_result": self.dfa_result,
            "regex_result": self.regex_result,
            "validation_result": self.validation_result,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

