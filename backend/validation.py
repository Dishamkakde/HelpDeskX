import re
from typing import Dict, Any, Tuple
from .dfa import dfa_validator

REGEX_PATTERN = r"^[A-Z]{2}-[0-9]{3}-[HML]$"
COMPILED_REGEX = re.compile(REGEX_PATTERN)

def validate_regex(identifier: str) -> Tuple[bool, str]:
    """
    Validates ticket identifier using regular expression: ^[A-Z]{2}-[0-9]{3}-[HML]$
    """
    if not identifier or not isinstance(identifier, str):
        return False, "Regex rejected: Empty identifier"

    if bool(COMPILED_REGEX.fullmatch(identifier)):
        return True, "Regex accepted: Matched pattern ^[A-Z]{2}-[0-9]{3}-[HML]$"
    else:
        return False, "Regex rejected: Did not match pattern ^[A-Z]{2}-[0-9]{3}-[HML]$"

def validate_ticket_identifier(identifier: str) -> Dict[str, Any]:
    """
    Executes both DFA and Regex validators independently.
    Verifies agreement between both theoretical models.
    """
    clean_id = identifier or ""

    # 1. Run DFA
    dfa_valid, dfa_reason, dfa_history = dfa_validator.validate(clean_id)
    dfa_result = "VALID" if dfa_valid else "INVALID"

    # 2. Run Regex
    regex_valid, regex_reason = validate_regex(clean_id)
    regex_result = "VALID" if regex_valid else "INVALID"

    # 3. Verify Agreement
    agreement = (dfa_valid == regex_valid)
    
    if not agreement:
        final_status = "REJECTED"
        final_reason = f"INTERNAL VALIDATION DISCREPANCY: DFA returned {dfa_result} but Regex returned {regex_result}."
    elif dfa_valid and regex_valid:
        final_status = "PASSED"
        final_reason = "Both DFA and Regex independently verified and accepted ticket identifier."
    else:
        final_status = "REJECTED"
        final_reason = f"Identifier rejected: {dfa_reason}"

    # Parse components if valid
    dept_code = clean_id[0:2] if len(clean_id) >= 2 else None
    issue_code = clean_id[3:6] if len(clean_id) >= 6 else None
    priority_code = clean_id[7] if len(clean_id) >= 8 else None

    return {
        "identifier": clean_id,
        "is_valid": (final_status == "PASSED"),
        "dfa_result": dfa_result,
        "regex_result": regex_result,
        "validation_status": final_status,
        "validation_reason": final_reason,
        "agreement": agreement,
        "department_code": dept_code,
        "issue_code": issue_code,
        "priority_code": priority_code,
        "dfa_transition_history": dfa_history
    }
