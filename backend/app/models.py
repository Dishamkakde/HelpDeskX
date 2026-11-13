from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=5, max_length=2000)
    requester_id: str = Field(..., min_length=2, max_length=50)
    requester_name: str = Field(..., min_length=2, max_length=100)
    requester_dept: str = Field(..., min_length=2, max_length=100)
    category: Optional[str] = None  # If None, automatically classified by DFA/Regex
    priority: Optional[str] = None  # If None, automatically inferred
    preferred_classifier: Optional[str] = "HYBRID"  # "DFA", "REGEX", or "HYBRID"

class TicketStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|RESOLVED|CLOSED|ESCALATED)$")
    note: Optional[str] = None

class TicketReassign(BaseModel):
    agent_id: int
    reason: Optional[str] = "Manual reassignment"

class TicketEscalate(BaseModel):
    reason: str = Field(..., min_length=3)
    target_team: Optional[str] = "Level-2 Escalations"

class PriorityOverride(BaseModel):
    new_priority: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    reason: str = Field(..., min_length=3)

class TicketNoteCreate(BaseModel):
    note: str = Field(..., min_length=2)

class ClassificationRequest(BaseModel):
    text: str = Field(..., min_length=1)
    engine: Optional[str] = "HYBRID"  # "DFA", "REGEX", "HYBRID", "ALL"

class ConcurrentSubmissionRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=30)
    category: Optional[str] = None
    priority: Optional[str] = None
