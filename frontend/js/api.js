/**
 * HelpDeskX REST API Client
 */
const API = {
  getCurrentRole() {
    const select = document.getElementById("role-select");
    return select ? select.value : "admin";
  },

  async request(endpoint, options = {}) {
    const role = this.getCurrentRole();
    const headers = {
      "Content-Type": "application/json",
      "X-User-Role": role,
      ...(options.headers || {})
    };

    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(endpoint, config);
      const data = await response.json();
      
      if (!response.ok) {
        const errorMsg = data.detail || (Array.isArray(data) ? JSON.stringify(data) : "API Error occurred");
        throw new Error(errorMsg);
      }
      return data;
    } catch (err) {
      console.error(`[API Error] ${endpoint}:`, err);
      throw err;
    }
  },

  // Health
  getHealth() {
    return this.request("/api/health");
  },

  // Dashboard Stats
  getDashboardStats() {
    return this.request("/api/dashboard/stats");
  },

  // Tickets
  getTickets(params = {}) {
    const searchParams = new URLSearchParams();
    if (params.category) searchParams.append("category", params.category);
    if (params.status) searchParams.append("status", params.status);
    if (params.priority) searchParams.append("priority", params.priority);
    if (params.search) searchParams.append("search", params.search);
    
    const query = searchParams.toString();
    return this.request(`/api/tickets${query ? "?" + query : ""}`);
  },

  getTicketDetails(ticketId) {
    return this.request(`/api/tickets/${ticketId}`);
  },

  createTicket(payload) {
    return this.request("/api/tickets", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  updateTicketStatus(ticketId, payload) {
    return this.request(`/api/tickets/${ticketId}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    });
  },

  reassignTicket(ticketId, payload) {
    return this.request(`/api/tickets/${ticketId}/reassign`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  escalateTicket(ticketId, payload) {
    return this.request(`/api/tickets/${ticketId}/escalate`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  overridePriority(ticketId, payload) {
    return this.request(`/api/tickets/${ticketId}/override-priority`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  addTicketNote(ticketId, payload) {
    return this.request(`/api/tickets/${ticketId}/notes`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  // Teams & Capacity
  getTeams() {
    return this.request("/api/teams");
  },

  // Classifier Studio
  classifyText(payload) {
    return this.request("/api/classify", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  getDFATrace(token) {
    return this.request(`/api/dfa/trace?token=${encodeURIComponent(token)}`);
  },

  getDFASpec() {
    return this.request("/api/dfa/spec");
  },

  // Concurrency Simulator
  simulateConcurrent(payload) {
    return this.request("/api/simulate/concurrent-submissions", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  resetDemo() {
    return this.request("/api/system/reset-demo", {
      method: "POST"
    });
  }
};
