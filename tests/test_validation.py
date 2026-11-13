 import pytest
from backend.dfa import dfa_validator, TicketIdentifierDFA
from backend.validation import validate_ticket_identifier, validate_regex

class TestDFAAndRegexValidation:
    """
    BCS503: Automata Theory & Computability
    Covers Test Cases 1 - 8
    """

    # Test Case 1: Valid ticket identifiers
    @pytest.mark.parametrize("valid_id,dept,issue,prio", [
        ("CS-101-H", "CS", "101", "H"),
        ("IT-205-M", "IT", "205", "M"),
        ("HR-999-L", "HR", "999", "L"),
        ("EC-123-H", "EC", "123", "H"),
        ("ME-456-M", "ME", "456", "M"),
        ("EE-789-L", "EE", "789", "L"),
    ])
    def test_case_01_valid_ticket_identifiers(self, valid_id, dept, issue, prio):
        res = validate_ticket_identifier(valid_id)
        assert res["is_valid"] is True
        assert res["dfa_result"] == "VALID"
        assert res["regex_result"] == "VALID"
        assert res["validation_status"] == "PASSED"
        assert res["department_code"] == dept
        assert res["issue_code"] == issue
        assert res["priority_code"] == prio

    # Test Case 2: Invalid department format (single letter or numbers in dept)
    @pytest.mark.parametrize("invalid_id", ["C-101-H", "1S-101-H", "C1-101-H", "CSC-101-H"])
    def test_case_02_invalid_department_format(self, invalid_id):
        res = validate_ticket_identifier(invalid_id)
        assert res["is_valid"] is False
        assert res["dfa_result"] == "INVALID"
        assert res["regex_result"] == "INVALID"
        assert res["validation_status"] == "REJECTED"

    # Test Case 3: Invalid issue code (less than 3 digits, letters instead of digits)
    @pytest.mark.parametrize("invalid_id", ["CS-10-H", "CS-1-H", "CS-ABC-H", "CS-1A2-H", "CS-1000-H"])
    def test_case_03_invalid_issue_code(self, invalid_id):
        res = validate_ticket_identifier(invalid_id)
        assert res["is_valid"] is False
        assert res["dfa_result"] == "INVALID"
        assert res["regex_result"] == "INVALID"

    # Test Case 4: Invalid priority (not in {H, M, L})
    @pytest.mark.parametrize("invalid_id", ["CS-101-X", "CS-101-A", "CS-101-9", "CS-101-Z"])
    def test_case_04_invalid_priority(self, invalid_id):
        res = validate_ticket_identifier(invalid_id)
        assert res["is_valid"] is False
        assert res["dfa_result"] == "INVALID"
        assert res["regex_result"] == "INVALID"

    # Test Case 5: Lowercase identifier
    @pytest.mark.parametrize("invalid_id", ["cs-101-h", "Cs-101-H", "CS-101-h", "cs-101-m"])
    def test_case_05_lowercase_identifier(self, invalid_id):
        res = validate_ticket_identifier(invalid_id)
        assert res["is_valid"] is False
        assert res["dfa_result"] == "INVALID"
        assert res["regex_result"] == "INVALID"

    # Test Case 6: Missing hyphen
    @pytest.mark.parametrize("invalid_id", ["CS101H", "CS-101H", "CS101-H", "CS 101 H"])
    def test_case_06_missing_hyphen(self, invalid_id):
        res = validate_ticket_identifier(invalid_id)
        assert res["is_valid"] is False
        assert res["dfa_result"] == "INVALID"
        assert res["regex_result"] == "INVALID"

    # Test Case 7: Extra characters
    @pytest.mark.parametrize("invalid_id", ["CS-101-HH", "CS-101-H-EXTRA", "CS-101-H1", "CS-101-H "])
    def test_case_07_extra_characters(self, invalid_id):
        res = validate_ticket_identifier(invalid_id)
        assert res["is_valid"] is False
        assert res["dfa_result"] == "INVALID"
        assert res["regex_result"] == "INVALID"

    # Test Case 8: DFA and Regex agreement across valid and invalid inputs
    @pytest.mark.parametrize("test_id", [
        "CS-101-H", "IT-205-M", "HR-999-L", "EC-123-H",
        "C-101-H", "CS-10-H", "CS-101-X", "cs-101-h", "CS101H", "CS-101-HH", "CS-ABC-H"
    ])
    def test_case_08_dfa_and_regex_agreement(self, test_id):
        dfa_valid, _, _ = dfa_validator.validate(test_id)
        regex_valid, _ = validate_regex(test_id)
        assert dfa_valid == regex_valid, f"Discrepancy on {test_id}: DFA={dfa_valid}, Regex={regex_valid}"

