import pytest
from backend.classification import classify_report

class TestReportClassification:
    """
    Covers Test Cases 9 - 14
    Verifies 5 Predefined Categories:
    HARDWARE, SOFTWARE, NETWORK, ACCESS, OTHER
    and Priority Rule: ACCESS -> NETWORK -> HARDWARE -> SOFTWARE -> OTHER
    """

    # Test Case 9: Hardware classification
    def test_case_09_hardware_classification(self):
        desc = "The computer monitor screen is flickering and mouse keyboard are not responding."
        res = classify_report(desc)
        assert res["category"] == "HARDWARE"
        assert any(k in res["matched_keywords"] for k in ["monitor", "screen", "keyboard", "mouse"])

    # Test Case 10: Software classification
    def test_case_10_software_classification(self):
        desc = "Fatal application crash during software update with an unexpected bug in the program."
        res = classify_report(desc)
        assert res["category"] == "SOFTWARE"
        assert any(k in res["matched_keywords"] for k in ["crash", "software", "update", "bug"])

    # Test Case 11: Network classification
    def test_case_11_network_classification(self):
        desc = "Unable to connect to company VPN over wifi router connectivity is lost."
        res = classify_report(desc)
        assert res["category"] == "NETWORK"
        assert any(k in res["matched_keywords"] for k in ["vpn", "wifi", "router", "connectivity"])

    # Test Case 12: Access classification
    def test_case_12_access_classification(self):
        desc = "Need account password reset because authentication failed and login access is blocked."
        res = classify_report(desc)
        assert res["category"] == "ACCESS"
        assert any(k in res["matched_keywords"] for k in ["password", "login", "access", "authentication"])

    # Test Case 13: Other classification (no matching domain keywords)
    def test_case_13_other_classification(self):
        desc = "General inquiry regarding campus schedule and room reservation timings."
        res = classify_report(desc)
        assert res["category"] == "OTHER"
        assert len(res["matched_keywords"]) == 0

    # Test Case 14: Multiple category matches with deterministic priority arbitration
    # Rule: ACCESS -> NETWORK -> HARDWARE -> SOFTWARE -> OTHER
    def test_case_14_multiple_matches_priority(self):
        # 1. Access + Network + Hardware + Software -> ACCESS wins!
        desc_all = "Cannot login to VPN from laptop after software installation crashed."
        res1 = classify_report(desc_all)
        assert res1["category"] == "ACCESS"

        # 2. Network + Hardware + Software -> NETWORK wins!
        desc_net_hw_sw = "Wifi on laptop failed while application was running."
        res2 = classify_report(desc_net_hw_sw)
        assert res2["category"] == "NETWORK"

        # 3. Hardware + Software -> HARDWARE wins!
        desc_hw_sw = "Laptop monitor went black when running the new program."
        res3 = classify_report(desc_hw_sw)
        assert res3["category"] == "HARDWARE"

