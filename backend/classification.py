import re
from datetime import datetime
from typing import Dict, List, Any

# Section 7 exact predefined keywords
CATEGORY_KEYWORDS = {
    "ACCESS": [
        "password", "login", "account", "permission", "access", "authentication"
    ],
    "NETWORK": [
        "wifi", "internet", "lan", "vpn", "router", "connectivity", "network"
    ],
    "HARDWARE": [
        "laptop", "computer", "keyboard", "mouse", "printer", "monitor", "motherboard", "screen"
    ],
    "SOFTWARE": [
        "software", "application", "installation", "update", "crash", "bug", "program"
    ]
}

# Fixed deterministic priority order
CLASSIFICATION_PRIORITY = ["ACCESS", "NETWORK", "HARDWARE", "SOFTWARE"]

def classify_report(description: str) -> Dict[str, Any]:
    """
    Classifies IT problem statement into exactly one of 5 categories:
    ACCESS, NETWORK, HARDWARE, SOFTWARE, OTHER.
    Applies fixed priority: ACCESS -> NETWORK -> HARDWARE -> SOFTWARE -> OTHER.
    """
    text = (description or "").lower()
    matches_by_category: Dict[str, List[str]] = {}

    for cat in CLASSIFICATION_PRIORITY:
        keywords = CATEGORY_KEYWORDS[cat]
        found = []
        for kw in keywords:
            # Word boundary regex check
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, text):
                found.append(kw)
        if found:
            matches_by_category[cat] = found

    # Apply deterministic priority: ACCESS -> NETWORK -> HARDWARE -> SOFTWARE -> OTHER
    chosen_category = "OTHER"
    matched_keywords = []

    for cat in CLASSIFICATION_PRIORITY:
        if cat in matches_by_category:
            chosen_category = cat
            matched_keywords = matches_by_category[cat]
            break

    return {
        "original_description": description,
        "category": chosen_category,
        "matched_keywords": matched_keywords,
        "all_category_matches": matches_by_category,
        "classification_priority_rule": "ACCESS -> NETWORK -> HARDWARE -> SOFTWARE -> OTHER",
        "timestamp": datetime.utcnow().isoformat()
    }

