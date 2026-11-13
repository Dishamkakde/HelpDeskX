# HelpDeskX — Intelligent IT Helpdesk Ticket Router

**Academic Engineering Demonstration**  
*Integrating Automata Theory & Computability (BCS503), Computer Networks (BCS502), Full-Stack Development, and Software Quality Auditing.*

---

## 1. Project Overview & System Architecture

HelpDeskX is an enterprise-grade automated IT helpdesk management platform. At the beginning of an academic semester, educational and corporate institutions face thousands of simultaneous IT support requests (faulty computers, software crashes, network/Wi-Fi downtime, password lockouts). Manual triage introduces severe bottlenecks and uneven technician workload. 

HelpDeskX automates the entire lifecycle:
1. **Intelligent Ingestion & Lexical Validation (BCS503)**: Validates incoming ticket identifiers using a formal Deterministic Finite Automaton (DFA) state machine and Regular Expressions.
2. **Deterministic Five-Category Classification**: Dispatches requests into `HARDWARE`, `SOFTWARE`, `NETWORK`, `ACCESS`, or `OTHER` with strict priority arbitration (`ACCESS → NETWORK → HARDWARE → SOFTWARE → OTHER`).
3. **Computer Networks Routing & Dispatch (BCS502)**: Routes tickets to one of 4 dedicated helpdesk teams using a configurable routing table based on Department Code and Issue Category.
4. **8-Ticket Team Capacity & Backup Overflow**: Strict enforcement of a maximum capacity of **8 OPEN tickets per team**. Overflow automatically diverts to designated Backup teams.
5. **Level-2 Escalation**: When all 4 primary teams and backup handlers reach saturation, tickets are automatically escalated to Level-2 Support.
6. **Real-Time SQLite Persistence**: Every action, status transition (`Pending → Assigned → In Progress → Resolved`), validation trace, and escalation is stored in SQLite via SQLAlchemy ORM.

---

## 2. Technology Stack & Architectural Decision

| Component | Technology | Rationale |
|---|---|---|
| **Backend** | Python Flask, Flask-CORS, RESTful API | Provides native execution for the manual Python DFA validator and Regex engine. |
| **Database** | SQLite + SQLAlchemy ORM | Lightweight, zero-config relational persistence with strict ACID transactions. |
| **Automata Engine** | Custom Python DFA & `re.fullmatch` | Formal mathematical state machine $M = (Q, \Sigma, \delta, q_0, F)$ without external libraries. |
| **Frontend** | Vanilla JS, Modern CSS, Chart.js | Clean, zero-build enterprise SaaS UI matching the `#10243B` Navy and `#269B83` Teal palette. |
| **Testing Suite** | `pytest` | 58 comprehensive automated tests covering all 24 required test specifications. |

---

## 3. Demo Accounts & Credentials

The system comes pre-seeded with 3 primary roles:

| Role | Account Email | Password | Permissions |
|---|---|---|---|
| **Administrator** | `admin@helpdeskx.com` | `Admin@123` | Full access, routing tables, teams, handlers, priority overrides, analytics |
| **Staff / User** | `staff@helpdeskx.com` | `Staff@123` | Submit IT complaints, live validation, track ticket status, timeline view |
| **Support Handler 1** | `handler1@helpdeskx.com` | `Handler@123` | View assigned workload (Team 1 - Hardware), update status, toggle availability |
| **Support Handler 2** | `handler2@helpdeskx.com` | `Handler@123` | Team 2 - Software Specialist |
| **Support Handler 3** | `handler3@helpdeskx.com` | `Handler@123` | Team 3 - Network Engineer |
| **Support Handler 4** | `handler4@helpdeskx.com` | `Handler@123` | Team 4 - Security & Access Analyst |

---

## 4. BCS503: Automata Theory & Computability Implementation

The ticket identifier adheres to the formal language:
$$L = \{ w_1 w_2 - d_1 d_2 d_3 - p \mid w_i \in [A-Z], d_i \in [0-9], p \in \{H, M, L\} \}$$
Example: `CS-101-H`, `IT-205-M`, `HR-999-L`.

### Formal 5-Tuple Definition: $M = (Q, \Sigma, \delta, q_0, F)$
- **States $Q$**: $\{q_0, q_1, q_2, q_3, q_4, q_5, q_6, q_7, q_8, q_9, q_D\}$
  - $q_0$: Initial state
  - $q_1$: First uppercase department letter
  - $q_2$: Second uppercase department letter
  - $q_3$: First hyphen delimiter (`-`)
  - $q_4$: First numeric digit
  - $q_5$: Second numeric digit
  - $q_6$: Third numeric digit
  - $q_7$: Second hyphen delimiter (`-`)
  - $q_8$: Priority character (`H`, `M`, or `L`)
  - $q_9$: Accepting state (EOF reached successfully)
  - $q_D$: Dead/Trap state (any invalid, unexpected, or extra characters)
- **Alphabet $\Sigma$**: $[A-Z0-9-HML]$
- **Transition Function $\delta$**: Implemented manually in `backend/dfa.py`.
- **Validation Agreement**: Both DFA and Regex (`^[A-Z]{2}-[0-9]{3}-[HML]$`) execute independently. If any discrepancy occurs, the submission is rejected.

---

## 5. BCS502: Computer Networks — Routing & Dispatch

### Configurable Routing Table
| Department | Category | Primary Team (8 Cap) | Backup Team |
|---|---|---|---|
| `CS` | `HARDWARE` | Team 1 | Team 2 |
| `CS` | `SOFTWARE` | Team 2 | Team 1 |
| `IT` | `NETWORK` | Team 3 | Team 4 |
| `HR` | `ACCESS` | Team 4 | Team 2 |
| `EC` | `HARDWARE` | Team 1 | Team 3 |
| `EC` | `NETWORK` | Team 3 | Team 1 |
| `ANY` | `OTHER` | Team 4 (Central Fallback) | Team 1 |

### 8-Ticket Capacity & Overflow Routing
- **Capacity**: Each of the 4 teams has a hard limit of **8 OPEN tickets** (`Pending`, `Assigned`, `In Progress`). `Resolved` tickets do not consume capacity.
- **Backup Routing**: If the primary team reaches 8 open tickets, the ticket routes to the configured Backup team.
- **Level-2 Escalation**: If all 4 teams reach saturation (32 active tickets), subsequent tickets escalate to the Level-2 Escalation Queue with an alert reason.

---

## 6. How to Run & Test the Application

### 1. Initialize Database & Seed Demo Data
```bash
python -m backend.seed
```

### 2. Run the Master Automated Test Suite
```bash
python -m pytest -v
```
*Executes all 58 unit and integration tests covering the 24 evaluation criteria.*

### 3. Start the Flask Server
```bash
python -m backend.app
```
*Access the application in your browser at `http://127.0.0.1:5000`.*

