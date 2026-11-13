import re
import time
from typing import Dict, List, Tuple, Any, Optional

# Formal Categories
CATEGORIES = [
    "HARDWARE",
    "SOFTWARE",
    "NETWORK",
    "ACCESS_SECURITY",
    "BILLING_ACCOUNT"
]

# Keywords for each Category
KEYWORD_DEFINITIONS: Dict[str, List[str]] = {
    "HARDWARE": [
        "laptop", "monitor", "keyboard", "mouse", "printer", "screen",
        "charger", "battery", "ram", "cpu", "disk", "hardware",
        "power", "overheating", "cable", "webcam", "headphone"
    ],
    "SOFTWARE": [
        "install", "crash", "bug", "error", "windows", "linux", "mac",
        "license", "update", "software", "driver", "freeze", "compiler",
        "exception", "patch", "application", "corrupted"
    ],
    "NETWORK": [
        "wifi", "vpn", "internet", "network", "dns", "router",
        "ethernet", "firewall", "latency", "ping", "bandwidth",
        "connection", "ip", "gateway", "disconnect", "packet"
    ],
    "ACCESS_SECURITY": [
        "password", "login", "permission", "2fa", "mfa", "auth",
        "access", "credentials", "unauthorized", "badge", "lockout",
        "security", "privilege", "authenticator", "reset", "denied"
    ],
    "BILLING_ACCOUNT": [
        "invoice", "payment", "billing", "subscription", "refund",
        "charge", "account", "receipt", "pricing", "expense",
        "payroll", "credit", "debit", "transaction", "balance"
    ]
}

class DFANode:
    __slots__ = ('state_id', 'transitions', 'is_accepting', 'category', 'keyword')
    def __init__(self, state_id: str):
        self.state_id = state_id
        self.transitions: Dict[str, 'DFANode'] = {}
        self.is_accepting: bool = False
        self.category: Optional[str] = None
        self.keyword: Optional[str] = None

class TicketDFA:
    """
    Formal Deterministic Finite Automaton (DFA) M = (Q, Sigma, delta, q0, F)
    for multi-keyword lexical analysis and classification into 5 categories.
    """
    def __init__(self):
        self.q0 = DFANode("q0")
        self.states: Dict[str, DFANode] = {"q0": self.q0}
        self.accepting_states: Dict[str, str] = {}  # state_id -> category
        self.alphabet = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
        self._state_counter = 1
        self._build_dfa()

    def _get_or_create_state(self, state_id: str) -> DFANode:
        if state_id not in self.states:
            node = DFANode(state_id)
            self.states[state_id] = node
        return self.states[state_id]

    def _build_dfa(self):
        """Constructs DFA state graph from defined vocabulary."""
        for cat, keywords in KEYWORD_DEFINITIONS.items():
            for kw in keywords:
                current = self.q0
                prefix = ""
                for char in kw.lower():
                    prefix += char
                    if char not in current.transitions:
                        state_name = f"q_{cat[:3]}_{prefix}"
                        new_node = self._get_or_create_state(state_name)
                        current.transitions[char] = new_node
                    current = current.transitions[char]
                
                # Mark as accept state for category
                current.is_accepting = True
                current.category = cat
                current.keyword = kw
                self.accepting_states[current.state_id] = cat

    def get_formal_spec(self) -> Dict[str, Any]:
        """Returns the formal mathematical 5-tuple M = (Q, Sigma, delta, q0, F)."""
        return {
            "Q_total_states": len(self.states),
            "Sigma_alphabet_size": len(self.alphabet),
            "q0": "q0",
            "F_accept_states_count": len(self.accepting_states),
            "categories": CATEGORIES,
            "sample_transitions_count": sum(len(n.transitions) for n in self.states.values())
        }

    def trace_token(self, token: str) -> Tuple[Optional[str], Optional[str], List[Dict[str, str]]]:
        """
        Runs DFA on a single token, generating state transition trace.
        Returns: (accepted_category, matched_keyword, transition_steps)
        """
        trace = []
        current = self.q0
        clean_token = token.lower().strip()
        
        for idx, char in enumerate(clean_token):
            prev_state = current.state_id
            if char in current.transitions:
                current = current.transitions[char]
                trace.append({
                    "step": idx + 1,
                    "char": char,
                    "from_state": prev_state,
                    "to_state": current.state_id,
                    "is_accepting": current.is_accepting
                })
            else:
                trace.append({
                    "step": idx + 1,
                    "char": char,
                    "from_state": prev_state,
                    "to_state": "TRAP",
                    "is_accepting": False
                })
                return None, None, trace
        
        if current.is_accepting:
            return current.category, current.keyword, trace
        return None, None, trace

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Runs DFA classification across the input text.
        Tokenizes into words and runs token-level DFA transitions.
        """
        start_time = time.perf_counter()
        
        # Tokenize preserving alphanumeric sequences
        tokens = re.findall(r'[a-zA-Z0-9_\-]+', text)
        category_hits: Dict[str, int] = {cat: 0 for cat in CATEGORIES}
        matched_keywords: List[Dict[str, Any]] = []
        full_transition_trace: List[Dict[str, Any]] = []
        
        for token in tokens:
            cat, kw, trace = self.trace_token(token)
            if cat and kw:
                category_hits[cat] += 1
                matched_keywords.append({
                    "token": token,
                    "keyword": kw,
                    "category": cat
                })
            # Collect sample trace for up to first 5 tokens
            if len(full_transition_trace) < 5 and trace:
                full_transition_trace.append({
                    "token": token,
                    "matched": bool(cat),
                    "steps": trace
                })
                
        total_hits = sum(category_hits.values())
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

        if total_hits == 0:
            return {
                "category": "HARDWARE",  # default fallback category
                "confidence": 0.20,
                "is_fallback": True,
                "category_scores": category_hits,
                "matched_keywords": [],
                "total_matches": 0,
                "execution_time_ms": elapsed_ms,
                "sample_trace": full_transition_trace,
                "engine": "DFA"
            }

        # Select highest scoring category
        best_category = max(category_hits, key=category_hits.get)
        confidence = round(category_hits[best_category] / total_hits, 3)

        return {
            "category": best_category,
            "confidence": max(confidence, 0.60),
            "is_fallback": False,
            "category_scores": category_hits,
            "matched_keywords": matched_keywords,
            "total_matches": total_hits,
            "execution_time_ms": elapsed_ms,
            "sample_trace": full_transition_trace,
            "engine": "DFA"
        }

# Global singleton DFA instance
dfa_instance = TicketDFA()

def classify_text_dfa(text: str) -> Dict[str, Any]:
    return dfa_instance.classify(text)

def get_dfa_trace(token: str) -> Dict[str, Any]:
    cat, kw, trace = dfa_instance.trace_token(token)
    return {
        "token": token,
        "category": cat,
        "keyword": kw,
        "is_accepted": bool(cat),
        "steps": trace,
        "step_count": len(trace)
    }
