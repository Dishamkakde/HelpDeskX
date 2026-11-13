/**
 * HelpDeskX — Intelligent IT Helpdesk Ticket Router
 * Frontend Application Controller
 */

// Application State
const State = {
  currentUser: JSON.parse(localStorage.getItem("helpdeskx_user") || "null"),
  token: localStorage.getItem("helpdeskx_token") || null,
  activePage: "staff-dashboard",
  charts: {}
};

// API Client Helper
const API = {
  async request(endpoint, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {})
    };

    if (State.token) {
      headers["Authorization"] = `Bearer ${State.token}`;
    }

    // Pass role header
    const auditRole = document.getElementById("quick-role-toggle")?.value || State.currentUser?.role || "ADMIN";
    headers["X-User-Role"] = auditRole;

    try {
      const res = await fetch(endpoint, { ...options, headers });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "An API error occurred");
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }
};

// UI Notifications
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  const bgColor = type === "error" ? "var(--red)" : (type === "warning" ? "var(--amber)" : "var(--teal)");
  toast.style.cssText = `
    background-color: ${bgColor};
    color: #FFFFFF;
    padding: 0.75rem 1.25rem;
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
    font-weight: 600;
    box-shadow: var(--shadow-dropdown);
    display: flex;
    align-items: center;
    gap: 0.5rem;
    animation: slideIn 0.2s ease;
  `;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ==================== AUTHENTICATION ====================

function checkAuth() {
  const loginView = document.getElementById("view-login");
  const appContainer = document.getElementById("app-authenticated");

  if (!State.token || !State.currentUser) {
    loginView.style.display = "flex";
    appContainer.style.display = "none";
  } else {
    loginView.style.display = "none";
    appContainer.style.display = "flex";

    // Update user info
    document.getElementById("current-user-name").textContent = State.currentUser.name;
    document.getElementById("current-user-role").textContent = State.currentUser.role;
    const roleToggle = document.getElementById("quick-role-toggle");
    if (roleToggle) roleToggle.value = State.currentUser.role;

    // Load initial page
    switchPage(State.activePage);
  }
}

async function handleLogin(email, password) {
  const errorBox = document.getElementById("login-error-msg");
  errorBox.style.display = "none";

  try {
    const data = await API.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    State.token = data.token;
    State.currentUser = data.user;
    localStorage.setItem("helpdeskx_token", data.token);
    localStorage.setItem("helpdeskx_user", JSON.stringify(data.user));

    showToast(`Welcome, ${data.user.name}! Role: ${data.user.role}`);
    
    // Redirect based on role
    if (data.user.role === "HANDLER") {
      State.activePage = "handler-dashboard";
    } else if (data.user.role === "ADMIN") {
      State.activePage = "routing-management";
    } else {
      State.activePage = "staff-dashboard";
    }

    checkAuth();
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.style.display = "block";
  }
}

function handleLogout() {
  State.token = null;
  State.currentUser = null;
  localStorage.removeItem("helpdeskx_token");
  localStorage.removeItem("helpdeskx_user");
  showToast("Logged out successfully");
  checkAuth();
}

// ==================== PAGE NAVIGATION ====================

function switchPage(pageId) {
  State.activePage = pageId;

  // Update Sidebar Links
  document.querySelectorAll(".nav-link").forEach(link => {
    if (link.dataset.page === pageId) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });

  // Update Visible Page View
  document.querySelectorAll(".page-view").forEach(view => {
    view.classList.remove("active");
  });

  const targetView = document.getElementById(`page-${pageId}`);
  if (targetView) targetView.classList.add("active");

  // Update Top Navbar Title
  const titles = {
    "staff-dashboard": "Staff Complaint Dashboard",
    "submit-ticket": "Submit IT Support Report",
    "track-ticket": "User Ticket Status Tracking",
    "handler-dashboard": "Support Handler Assigned Workload",
    "routing-management": "BCS502 Computer Networks — Routing & Capacity Dashboard",
    "analytics-dashboard": "Live Analytics & Performance Metrics",
    "team-management": "Team Roster & Handler Management",
    "automata-lab": "BCS503 Automata Theory — DFA Testing Studio"
  };
  document.getElementById("top-nav-page-title").textContent = titles[pageId] || "HelpDeskX";

  // Trigger page-specific data fetch
  if (pageId === "staff-dashboard") loadStaffDashboard();
  if (pageId === "handler-dashboard") loadHandlerDashboard();
  if (pageId === "routing-management") loadRoutingManagement();
  if (pageId === "analytics-dashboard") loadAnalyticsDashboard();
  if (pageId === "team-management") loadTeamManagement();
  if (pageId === "automata-lab") runLabTrace("CS-101-H");
}

// ==================== PAGE 2: STAFF DASHBOARD ====================

async function loadStaffDashboard() {
  try {
    const search = document.getElementById("dash-search")?.value || "";
    const category = document.getElementById("dash-filter-category")?.value || "";
    const status = document.getElementById("dash-filter-status")?.value || "";

    const query = new URLSearchParams();
    if (search) query.append("search", search);
    if (category) query.append("category", category);
    if (status) query.append("status", status);

    const tickets = await API.request(`/api/tickets?${query.toString()}`);
    
    // Compute stats
    const total = tickets.length;
    const pending = tickets.filter(t => t.status === "Pending").length;
    const assigned = tickets.filter(t => t.status === "Assigned").length;
    const inProgress = tickets.filter(t => t.status === "In Progress").length;
    const resolved = tickets.filter(t => t.status === "Resolved").length;

    document.getElementById("dash-stat-total").textContent = total;
    document.getElementById("dash-stat-pending").textContent = pending;
    document.getElementById("dash-stat-assigned").textContent = assigned;
    document.getElementById("dash-stat-progress").textContent = inProgress;
    document.getElementById("dash-stat-resolved").textContent = resolved;

    // Render Table
    const tbody = document.getElementById("dash-tickets-body");
    if (tickets.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No tickets matching filter criteria.</td></tr>`;
      return;
    }

    tbody.innerHTML = tickets.map(t => `
      <tr>
        <td><strong>${t.public_ticket_id}</strong></td>
        <td><code>${t.ticket_identifier}</code></td>
        <td><span class="badge badge-${t.category.toLowerCase()}">${t.category}</span></td>
        <td><span class="badge badge-prio-${t.priority.toLowerCase()}">${t.priority}</span></td>
        <td><span class="badge badge-${t.status.toLowerCase().replace(' ', '-')}">${t.status}</span></td>
        <td>${t.assigned_team_name || 'Unassigned'} &bull; <small>${t.assigned_handler_name || 'Queue'}</small></td>
        <td><small>${new Date(t.created_at).toLocaleString()}</small></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="trackTicketDirect('${t.public_ticket_id}')">
            Track
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(`Failed to load dashboard: ${err.message}`, "error");
  }
}

// ==================== PAGE 3: REPORT SUBMISSION & LIVE VALIDATION ====================

let validationDebounce = null;
async function performLiveValidation() {
  const ident = document.getElementById("sub-identifier").value.trim();
  const desc = document.getElementById("sub-description").value.trim();

  if (!ident) return;

  try {
    const valRes = await API.request("/api/validate", {
      method: "POST",
      body: JSON.stringify({ identifier: ident })
    });

    const clfRes = await API.request("/api/classify", {
      method: "POST",
      body: JSON.stringify({ description: desc || "computer" })
    });

    // Update UI elements
    const badge = document.getElementById("live-val-badge");
    const dfaSpan = document.getElementById("live-dfa-res");
    const regexSpan = document.getElementById("live-regex-res");
    const catSpan = document.getElementById("live-detected-cat");
    const prioSpan = document.getElementById("live-detected-prio");
    const reasonDiv = document.getElementById("live-val-reason");

    if (valRes.is_valid) {
      badge.textContent = "VALID";
      badge.className = "badge badge-software";
      dfaSpan.textContent = "VALID";
      dfaSpan.style.color = "var(--teal)";
      regexSpan.textContent = "VALID";
      regexSpan.style.color = "var(--teal)";
      reasonDiv.textContent = valRes.validation_reason;
      reasonDiv.style.color = "var(--text-muted)";
    } else {
      badge.textContent = "INVALID IDENTIFIER";
      badge.className = "badge badge-hardware";
      badge.style.backgroundColor = "#FEE2E2";
      badge.style.color = "var(--red)";
      dfaSpan.textContent = valRes.dfa_result;
      dfaSpan.style.color = "var(--red)";
      regexSpan.textContent = valRes.regex_result;
      regexSpan.style.color = "var(--red)";
      reasonDiv.textContent = valRes.validation_reason;
      reasonDiv.style.color = "var(--red)";
    }

    catSpan.textContent = clfRes.category;
    const prioMap = { "H": "HIGH (H)", "M": "MEDIUM (M)", "L": "LOW (L)" };
    prioSpan.textContent = prioMap[valRes.priority_code] || "MEDIUM (M)";

  } catch (err) {
    console.warn("Live validation error:", err);
  }
}

async function handleTicketSubmit(e) {
  e.preventDefault();

  const payload = {
    reporter_name: document.getElementById("sub-name").value.trim(),
    email: document.getElementById("sub-email").value.trim(),
    department: document.getElementById("sub-dept").value,
    ticket_identifier: document.getElementById("sub-identifier").value.trim(),
    issue_code: document.getElementById("sub-issue-code").value.trim(),
    description: document.getElementById("sub-description").value.trim()
  };

  try {
    const res = await API.request("/api/tickets", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast(`Ticket ${res.ticket.public_ticket_id} submitted and assigned!`);
    
    // Switch to tracking view to show complete timeline
    trackTicketDirect(res.ticket.public_ticket_id);
  } catch (err) {
    showToast(`Submission rejected: ${err.message}`, "error");
  }
}

// ==================== PAGE 4: USER TICKET TRACKING ====================

async function trackTicketDirect(ticketId) {
  switchPage("track-ticket");
  document.getElementById("track-search-input").value = ticketId;
  await performTracking(ticketId);
}

async function performTracking(ticketId) {
  try {
    const data = await API.request(`/api/tickets/track/${encodeURIComponent(ticketId)}`);
    document.getElementById("track-results-area").style.display = "block";

    // Update Details
    document.getElementById("track-detail-id").textContent = data.public_ticket_id;
    document.getElementById("track-detail-ident").textContent = data.ticket_identifier;
    document.getElementById("track-detail-cat").textContent = data.category;
    document.getElementById("track-detail-prio").textContent = data.priority;
    document.getElementById("track-detail-team").textContent = data.assigned_team_name || "Unassigned";
    document.getElementById("track-detail-handler").textContent = data.assigned_handler_name || "Support Pool";
    document.getElementById("track-detail-status").textContent = data.status;
    document.getElementById("track-detail-reporter").textContent = data.reporter_name;

    // Update Visual Timeline
    const steps = ["submitted", "validated", "assigned", "progress", "resolved"];
    const statusIdx = {
      "Pending": 1,
      "Assigned": 2,
      "In Progress": 3,
      "Resolved": 4
    }[data.status] || 0;

    steps.forEach((step, idx) => {
      const el = document.getElementById(`step-${step}`);
      if (!el) return;
      if (idx <= statusIdx) {
        el.className = "timeline-step completed";
      } else {
        el.className = "timeline-step";
      }
    });

    // Populate Status History Table
    const tbody = document.getElementById("track-history-body");
    if (!data.status_history || data.status_history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center;">No recorded status changes yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.status_history.map(h => `
      <tr>
        <td><small>${new Date(h.timestamp).toLocaleString()}</small></td>
        <td>${h.previous_status}</td>
        <td><strong>${h.new_status}</strong></td>
        <td>${h.changed_by}</td>
        <td>${h.notes || '—'}</td>
      </tr>
    `).join("");

  } catch (err) {
    showToast(err.message, "error");
    document.getElementById("track-results-area").style.display = "none";
  }
}

// ==================== PAGE 5: HANDLER DASHBOARD ====================

async function loadHandlerDashboard() {
  try {
    const tickets = await API.request("/api/tickets");
    const user = State.currentUser;

    const myTickets = tickets.filter(t => t.assigned_handler_id === user?.id || user?.role === "ADMIN");
    const activeCount = myTickets.filter(t => t.status !== "Resolved").length;

    document.getElementById("handler-stat-total").textContent = myTickets.length;
    document.getElementById("handler-stat-load").textContent = `${activeCount} / 8`;
    document.getElementById("handler-stat-avail").textContent = user?.is_available !== false ? "Available" : "Unavailable";

    const tbody = document.getElementById("handler-tickets-body");
    if (myTickets.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No active tickets assigned to you.</td></tr>`;
      return;
    }

    tbody.innerHTML = myTickets.map(t => `
      <tr>
        <td><strong>${t.public_ticket_id}</strong></td>
        <td>${t.department_code}</td>
        <td><span class="badge badge-${t.category.toLowerCase()}">${t.category}</span></td>
        <td><span class="badge badge-prio-${t.priority.toLowerCase()}">${t.priority}</span></td>
        <td>${t.description.length > 50 ? t.description.substring(0, 50) + '...' : t.description}</td>
        <td><small>${new Date(t.created_at).toLocaleDateString()}</small></td>
        <td><span class="badge badge-${t.status.toLowerCase().replace(' ', '-')}">${t.status}</span></td>
        <td>
          <button class="btn btn-navy btn-sm" onclick="openStatusModal(${t.id}, '${t.status}')">
            Update Status
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(`Failed to load handler tickets: ${err.message}`, "error");
  }
}

async function toggleMyAvailability() {
  try {
    const user = State.currentUser;
    const newAvail = !(user?.is_available !== false);
    const updated = await API.request(`/api/handlers/${user.id}/availability`, {
      method: "PATCH",
      body: JSON.stringify({ is_available: newAvail })
    });

    State.currentUser.is_available = updated.is_available;
    localStorage.setItem("helpdeskx_user", JSON.stringify(State.currentUser));
    showToast(`Availability status updated to: ${updated.is_available ? 'Available' : 'Unavailable'}`);
    loadHandlerDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==================== PAGE 6: ROUTING & CAPACITY (BCS502) ====================

async function loadRoutingManagement() {
  try {
    const [teams, rules, escalations] = await Promise.all([
      API.request("/api/teams"),
      API.request("/api/routing"),
      API.request("/api/escalations")
    ]);

    // 1. Render 4 Teams Capacity Cards
    const cardsContainer = document.getElementById("teams-capacity-cards");
    cardsContainer.innerHTML = teams.map(t => {
      const active = t.active_tickets_count;
      const cap = t.max_capacity;
      const pct = Math.round((active / cap) * 100);
      const color = active >= cap ? "var(--red)" : (active >= 6 ? "var(--amber)" : "var(--teal)");

      return `
        <div class="stat-card" style="border-top: 4px solid ${color};">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <strong style="color: var(--navy);">${t.team_name}</strong>
            <span class="badge ${t.is_available ? 'badge-software' : 'badge-hardware'}">
              ${t.is_available ? 'Active' : 'Offline'}
            </span>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 0.35rem;">
            <span style="font-size: 1.5rem; font-weight: 800; color: ${color};">${active} / ${cap}</span>
            <small style="color: var(--text-muted);">${pct}% Cap</small>
          </div>
          <div style="width: 100%; height: 6px; background-color: var(--border-light); border-radius: 999px; overflow: hidden; margin-bottom: 0.5rem;">
            <div style="width: ${Math.min(pct, 100)}%; height: 100%; background-color: ${color};"></div>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-light); display: flex; justify-content: space-between;">
            <span>RR Pointer: Handler #${t.round_robin_pointer}</span>
            <span>${t.remaining_capacity} slots left</span>
          </div>
        </div>
      `;
    }).join("");

    // 2. Render Routing Rules Table
    const rulesBody = document.getElementById("routing-rules-table-body");
    rulesBody.innerHTML = rules.map(r => `
      <tr>
        <td><strong>${r.department_code}</strong></td>
        <td><span class="badge badge-${r.category.toLowerCase()}">${r.category}</span></td>
        <td><strong>${r.primary_team_name}</strong> (Cap: 8)</td>
        <td>${r.backup_team_name} (Backup)</td>
        <td><span class="badge ${r.is_active ? 'badge-software' : 'badge-other'}">${r.is_active ? 'Active' : 'Disabled'}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="toggleRuleStatus(${r.id}, ${!r.is_active})">
            ${r.is_active ? 'Disable' : 'Enable'}
          </button>
        </td>
      </tr>
    `).join("");

    // 3. Render Escalations Queue
    const escBadge = document.getElementById("escalations-count-badge");
    escBadge.textContent = `${escalations.length} Active Escalations`;

    const escBody = document.getElementById("escalations-table-body");
    if (escalations.length === 0) {
      escBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No active Level-2 escalations. All teams operational.</td></tr>`;
      return;
    }

    escBody.innerHTML = escalations.map(e => `
      <tr>
        <td>#${e.id}</td>
        <td><strong>${e.ticket_public_id || 'HDX-TICKET'}</strong></td>
        <td>${e.department_code || 'CS'}</td>
        <td><span class="badge badge-${(e.category || 'hardware').toLowerCase()}">${e.category || 'HARDWARE'}</span></td>
        <td style="color: var(--red); font-size: 0.8rem;">${e.reason}</td>
        <td><small>${new Date(e.created_at).toLocaleTimeString()}</small></td>
        <td><span class="badge badge-pending">${e.status}</span></td>
        <td>
          <button class="btn btn-danger btn-sm" onclick="resolveEscalation(${e.id})">
            Resolve L2
          </button>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    showToast(`Failed to load routing data: ${err.message}`, "error");
  }
}

async function toggleRuleStatus(ruleId, newActive) {
  try {
    await API.request(`/api/routing/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: newActive })
    });
    showToast("Routing rule updated.");
    loadRoutingManagement();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function resolveEscalation(escId) {
  try {
    await API.request(`/api/escalations/${escId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action: "RESOLVE", notes: "Resolved by L2 Supervisor" })
    });
    showToast(`Escalation #${escId} resolved!`);
    loadRoutingManagement();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==================== PAGE 7: ANALYTICS DASHBOARD ====================

async function loadAnalyticsDashboard() {
  try {
    const data = await API.request("/api/analytics");

    // 1. Category Chart
    const ctxCat = document.getElementById("chart-categories")?.getContext("2d");
    if (ctxCat) {
      if (State.charts.cat) State.charts.cat.destroy();
      State.charts.cat = new Chart(ctxCat, {
        type: "doughnut",
        data: {
          labels: data.category_distribution.map(c => c.category),
          datasets: [{
            data: data.category_distribution.map(c => c.count),
            backgroundColor: ["#0284C7", "#16A34A", "#9333EA", "#E11D48", "#64748B"]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    // 2. Priority Chart
    const ctxPrio = document.getElementById("chart-priorities")?.getContext("2d");
    if (ctxPrio) {
      if (State.charts.prio) State.charts.prio.destroy();
      State.charts.prio = new Chart(ctxPrio, {
        type: "pie",
        data: {
          labels: data.priority_distribution.map(p => p.priority),
          datasets: [{
            data: data.priority_distribution.map(p => p.count),
            backgroundColor: ["#DC2626", "#D97706", "#64748B"]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    // 3. Department Chart
    const ctxDept = document.getElementById("chart-departments")?.getContext("2d");
    if (ctxDept) {
      if (State.charts.dept) State.charts.dept.destroy();
      State.charts.dept = new Chart(ctxDept, {
        type: "bar",
        data: {
          labels: data.department_distribution.map(d => d.department),
          datasets: [{
            label: "Complaints Count",
            data: data.department_distribution.map(d => d.count),
            backgroundColor: "#10243B"
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    // 4. Team Workload vs 8 Cap Chart
    const ctxTeam = document.getElementById("chart-team-workload")?.getContext("2d");
    if (ctxTeam) {
      if (State.charts.team) State.charts.team.destroy();
      State.charts.team = new Chart(ctxTeam, {
        type: "bar",
        data: {
          labels: data.team_workload.map(t => t.team_name),
          datasets: [
            {
              label: "Active Tickets",
              data: data.team_workload.map(t => t.active_tickets),
              backgroundColor: "#269B83"
            },
            {
              label: "Max Capacity (8)",
              data: data.team_workload.map(t => t.max_capacity),
              backgroundColor: "#E2E8F0"
            }
          ]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

  } catch (err) {
    showToast(`Failed to load analytics: ${err.message}`, "error");
  }
}

// ==================== PAGE 8: TEAM MANAGEMENT ====================

async function loadTeamManagement() {
  try {
    const handlers = await API.request("/api/handlers");
    const tbody = document.getElementById("handlers-table-body");

    tbody.innerHTML = handlers.map(h => `
      <tr>
        <td><strong>${h.name}</strong></td>
        <td><code>${h.email}</code></td>
        <td>${h.team_name || 'Team 1'}</td>
        <td>${h.department || 'IT'}</td>
        <td><strong>${h.active_tickets || 0}</strong> active</td>
        <td>
          <span class="badge ${h.is_available ? 'badge-software' : 'badge-hardware'}">
            ${h.is_available ? 'Available' : 'Unavailable'}
          </span>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="toggleHandlerAvail(${h.id}, ${!h.is_available})">
            Toggle Avail
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(`Failed to load team roster: ${err.message}`, "error");
  }
}

async function toggleHandlerAvail(handlerId, newAvail) {
  try {
    await API.request(`/api/handlers/${handlerId}/availability`, {
      method: "PATCH",
      body: JSON.stringify({ is_available: newAvail })
    });
    showToast("Handler availability updated.");
    loadTeamManagement();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==================== AUTOMATA LAB (BCS503) ====================

async function runLabTrace(identifier) {
  try {
    const res = await API.request("/api/validate", {
      method: "POST",
      body: JSON.stringify({ identifier })
    });

    const badge = document.getElementById("lab-final-status-badge");
    badge.textContent = res.validation_status;
    badge.className = res.is_valid ? "badge badge-software" : "badge badge-hardware";

    const tbody = document.getElementById("lab-trace-table-body");
    const steps = res.dfa_transition_history || [];

    if (steps.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center;">No transitions recorded.</td></tr>`;
      return;
    }

    const stateDescMap = {
      "q0": "Start State",
      "q1": "First Dept Letter Valid",
      "q2": "Second Dept Letter Valid",
      "q3": "First Hyphen Verified",
      "q4": "First Numeric Digit Valid",
      "q5": "Second Numeric Digit Valid",
      "q6": "Third Numeric Digit Valid",
      "q7": "Second Hyphen Verified",
      "q8": "Priority Code (H/M/L) Valid",
      "q9": "Accepting State (Valid Identifier)",
      "qD": "Dead / Trap State (Rejected)"
    };

    tbody.innerHTML = steps.map(s => `
      <tr>
        <td>#${s.step}</td>
        <td><code>${s.input_char === ' ' ? '[SPACE]' : s.input_char}</code></td>
        <td><code>${s.from_state}</code></td>
        <td><strong style="color: ${s.to_state === 'qD' ? 'var(--red)' : (s.to_state === 'q9' ? 'var(--green)' : 'var(--teal)')};">${s.to_state}</strong></td>
        <td>${stateDescMap[s.to_state] || 'Transition'}</td>
      </tr>
    `).join("");

  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==================== MODALS & ACTIONS ====================

function openStatusModal(ticketId, currentStatus) {
  document.getElementById("modal-ticket-id").value = ticketId;
  document.getElementById("modal-status-select").value = currentStatus === "Pending" ? "Assigned" : currentStatus;
  document.getElementById("modal-update-status").classList.add("active");
}

// Close Modals
document.addEventListener("click", e => {
  if (e.target.dataset.close) {
    const modalId = e.target.dataset.close;
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove("active");
  }
});

// Setup Event Listeners on DOM Load
document.addEventListener("DOMContentLoaded", () => {
  // Navigation Links
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", () => {
      switchPage(link.dataset.page);
    });
  });

  // Top New Report Button
  document.getElementById("btn-top-submit")?.addEventListener("click", () => {
    switchPage("submit-ticket");
  });

  // Quick Role Toggle for Evaluator
  document.getElementById("quick-role-toggle")?.addEventListener("change", e => {
    if (State.currentUser) {
      State.currentUser.role = e.target.value;
      localStorage.setItem("helpdeskx_user", JSON.stringify(State.currentUser));
      document.getElementById("current-user-role").textContent = e.target.value;
      showToast(`Role switched to: ${e.target.value}`);
    }
  });

  // Login Form
  document.getElementById("form-login")?.addEventListener("submit", e => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const pwd = document.getElementById("login-password").value;
    handleLogin(email, pwd);
  });

  // Password Visibility Toggle
  document.getElementById("btn-toggle-password")?.addEventListener("click", () => {
    const pwdInput = document.getElementById("login-password");
    const btn = document.getElementById("btn-toggle-password");
    if (pwdInput.type === "password") {
      pwdInput.type = "text";
      btn.textContent = "Hide";
    } else {
      pwdInput.type = "password";
      btn.textContent = "Show";
    }
  });

  // Demo Login Pills
  document.getElementById("pill-admin")?.addEventListener("click", () => {
    document.getElementById("login-email").value = "admin@helpdeskx.com";
    document.getElementById("login-password").value = "Admin@123";
    handleLogin("admin@helpdeskx.com", "Admin@123");
  });

  document.getElementById("pill-staff")?.addEventListener("click", () => {
    document.getElementById("login-email").value = "staff@helpdeskx.com";
    document.getElementById("login-password").value = "Staff@123";
    handleLogin("staff@helpdeskx.com", "Staff@123");
  });

  document.getElementById("pill-handler")?.addEventListener("click", () => {
    document.getElementById("login-email").value = "handler1@helpdeskx.com";
    document.getElementById("login-password").value = "Handler@123";
    handleLogin("handler1@helpdeskx.com", "Handler@123");
  });

  // Logout Button
  document.getElementById("btn-logout")?.addEventListener("click", handleLogout);

  // Live Validation on Ticket Form
  document.getElementById("sub-identifier")?.addEventListener("input", () => {
    clearTimeout(validationDebounce);
    validationDebounce = setTimeout(performLiveValidation, 200);
  });
  document.getElementById("sub-description")?.addEventListener("input", () => {
    clearTimeout(validationDebounce);
    validationDebounce = setTimeout(performLiveValidation, 250);
  });

  // Ticket Submit Form
  document.getElementById("form-submit-ticket")?.addEventListener("submit", handleTicketSubmit);

  // Prefill Invalid Test Button
  document.getElementById("btn-prefill-invalid")?.addEventListener("click", () => {
    document.getElementById("sub-identifier").value = "CS-10-X";
    performLiveValidation();
  });

  // Tracking Search Form
  document.getElementById("form-track-search")?.addEventListener("submit", e => {
    e.preventDefault();
    const id = document.getElementById("track-search-input").value.trim();
    if (id) performTracking(id);
  });

  // Dashboard Refresh & Filters
  document.getElementById("btn-refresh-dashboard")?.addEventListener("click", loadStaffDashboard);
  document.getElementById("dash-search")?.addEventListener("input", loadStaffDashboard);
  document.getElementById("dash-filter-category")?.addEventListener("change", loadStaffDashboard);
  document.getElementById("dash-filter-status")?.addEventListener("change", loadStaffDashboard);

  // Handler Page Actions
  document.getElementById("btn-toggle-my-avail")?.addEventListener("click", toggleMyAvailability);
  document.getElementById("btn-refresh-handler")?.addEventListener("click", loadHandlerDashboard);

  // Routing Management Refresh
  document.getElementById("btn-refresh-routing")?.addEventListener("click", loadRoutingManagement);

  // Analytics Refresh
  document.getElementById("btn-refresh-analytics")?.addEventListener("click", loadAnalyticsDashboard);

  // Handlers Roster Refresh
  document.getElementById("btn-refresh-handlers")?.addEventListener("click", loadTeamManagement);

  // Automata Lab Buttons
  document.getElementById("btn-run-lab-trace")?.addEventListener("click", () => {
    const val = document.getElementById("lab-test-id-input").value.trim();
    runLabTrace(val);
  });

  document.querySelectorAll(".lab-sample-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.getElementById("lab-test-id-input").value = btn.dataset.val;
      runLabTrace(btn.dataset.val);
    });
  });

  // Modal: Update Status Submit
  document.getElementById("form-modal-status")?.addEventListener("submit", async e => {
    e.preventDefault();
    const ticketId = document.getElementById("modal-ticket-id").value;
    const newStatus = document.getElementById("modal-status-select").value;
    const notes = document.getElementById("modal-status-notes").value;

    try {
      await API.request(`/api/tickets/${ticketId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus, notes })
      });
      showToast("Ticket status updated successfully!");
      document.getElementById("modal-update-status").classList.remove("active");
      loadHandlerDashboard();
      loadStaffDashboard();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Initial Check
  checkAuth();
  performLiveValidation();
});

