"""
Automata Theory and Computability (BCS503)
Manual DFA Implementation for HelpDeskX Ticket Identifier Validation.
Formal Model: M = (Q, Sigma, delta, q0, F)
Alphabet Sigma = [A-Z0-9-HML]
States Q = {q0, q1, q2, q3, q4, q5, q6, q7, q8, q9, qD}
Accept States F = {q9}
"""

from typing import Tuple, List, Dict, Any

class TicketIdentifierDFA:
    """
    Manual implementation of Deterministic Finite Automaton (DFA)
    for validating ticket identifiers in format: [A-Z]{2}-[0-9]{3}-[HML]
    e.g., CS-101-H, IT-205-M, HR-999-L
    """

    STATES = ["q0", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "qD"]
    START_STATE = "q0"
    ACCEPT_STATE = "q9"
    DEAD_STATE = "qD"

    @staticmethod
    def transition(current_state: str, char: str) -> str:
        """
        State transition function delta: Q x Sigma -> Q
        """
        if current_state == "q0":
            # First Department letter: [A-Z]
            if char.isupper() and char.isalpha():
                return "q1"
            return "qD"

        elif current_state == "q1":
            # Second Department letter: [A-Z]
            if char.isupper() and char.isalpha():
                return "q2"
            return "qD"

        elif current_state == "q2":
            # First Hyphen: '-'
            if char == "-":
                return "q3"
            return "qD"

        elif current_state == "q3":
            # First numeric digit: [0-9]
            if char.isdigit():
                return "q4"
            return "qD"

        elif current_state == "q4":
            # Second numeric digit: [0-9]
            if char.isdigit():
                return "q5"
            return "qD"

        elif current_state == "q5":
            # Third numeric digit: [0-9]
            if char.isdigit():
                return "q6"
            return "qD"

        elif current_state == "q6":
            # Second Hyphen: '-'
            if char == "-":
                return "q7"
            return "qD"

        elif current_state == "q7":
            # Priority code: [H, M, L]
            if char in ("H", "M", "L"):
                return "q8"
            return "qD"

        elif current_state == "q8":
            # Any character after priority leads to Dead/Reject state (reject extra characters)
            return "qD"

        elif current_state == "q9":
            # Already accepted, extra characters reject
            return "qD"

        elif current_state == "qD":
            # Dead state traps all subsequent characters
            return "qD"

        return "qD"

    def validate(self, identifier: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Processes string through DFA step-by-step.
        Returns: (is_valid, reason, state_transition_history)
        """
        if not identifier or not isinstance(identifier, str):
            return False, "Identifier cannot be empty", []

        current_state = self.START_STATE
        history = []

        for idx, char in enumerate(identifier):
            prev_state = current_state
            current_state = self.transition(current_state, char)
            
            history.append({
                "step": idx + 1,
                "input_char": char,
                "from_state": prev_state,
                "to_state": current_state,
                "is_dead": current_state == self.DEAD_STATE
            })

            # Early exit if trapped in Dead State
            if current_state == self.DEAD_STATE:
                reason = f"DFA rejected invalid character '{char}' at position {idx + 1} from state {prev_state}"
                return False, reason, history

        # After processing all characters, verify if in accept state
        # In our state machine, q8 is reached upon reading valid priority.
        # Moving to q9 represents successful completion of the input stream.
        if current_state == "q8":
            current_state = self.ACCEPT_STATE
            history.append({
                "step": len(identifier) + 1,
                "input_char": "EOF",
                "from_state": "q8",
                "to_state": self.ACCEPT_STATE,
                "is_dead": False
            })
            return True, "DFA accepted valid identifier", history

        # Incomplete string rejection
        return False, f"DFA rejected: Incomplete identifier reached state '{current_state}', expected accept state '{self.ACCEPT_STATE}'", history

    def get_formal_definition(self) -> Dict[str, Any]:
        """Returns mathematical 5-tuple specification for BCS503."""
        return {
            "name": "Ticket Identifier Validation DFA",
            "formal_5_tuple": "M = (Q, Sigma, delta, q0, F)",
            "Q": self.STATES,
            "Sigma": "[A-Z0-9-HML]",
            "q0": self.START_STATE,
            "F": [self.ACCEPT_STATE],
            "language": "L = { ww'-ddd-p | w,w' in [A-Z], d in [0-9], p in {H, M, L} }"
        }

# Global singleton instance
dfa_validator = TicketIdentifierDFA()

