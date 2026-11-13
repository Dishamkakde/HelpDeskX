import re
import time
from typing import Dict, List, Tuple, Any

REGEX_PATTERNS: Dict[str, List[Tuple[str, int, str]]] = {
    "HARDWARE": [
        (r"\b(laptop|desktop|pc|macbook|workstation)\b", 3, "computer_device"),
        (r"\b(monitor|screen|display|hdmi|vga|projector)\b", 3, "display_device"),
        (r"\b(keyboard|mouse|trackpad|peripheral)\b", 3, "input_device"),
        (r"\b(printer|scanner|toner|cartridge|paper\s*jam)\b", 4, "printing"),
        (r"\b(ram|memory|cpu|processor|motherboard|gpu)\b", 4, "internal_component"),
        (r"\b(hard\s*drive|ssd|disk|storage|flash\s*drive)\b", 3, "storage_hardware"),
        (r"\b(charger|battery|power\s*cable|surge\s*protector|adapter)\b", 3, "power_hardware"),
        (r"\b(overheat(ing)?|smoke|spark|hardware\s*fault|physical\s*damage)\b", 5, "hardware_failure"),
        (r"\b(headphone|webcam|camera|microphone|speaker)\b", 2, "audio_visual")
    ],
    "SOFTWARE": [
        (r"\b(install(ation|ing)?|uninstall|reinstall)\b", 3, "software_installation"),
        (r"\b(crash(es|ed|ing)?|bsod|blue\s*screen|freeze(s|ing)?)\b", 5, "crash_issue"),
        (r"\b(bug|glitch|corrupt(ion|ed)?|unhandled\s*exception|segfault)\b", 4, "software_bug"),
        (r"\b(windows\s*(10|11|server)?|linux|ubuntu|macos)\b", 3, "os_system"),
        (r"\b(license|product\s*key|activation|expired\s*license)\b", 4, "software_license"),
        (r"\b(update|upgrade|patch|version\s*mismatch)\b", 3, "software_update"),
        (r"\b(driver|firmware|dll\s*missing|runtime\s*error)\b", 4, "driver_runtime"),
        (r"\b(compiler|python|java|node|git|ide|vscode)\b", 3, "development_tools"),
        (r"\b(app|application|program|software\s*package)\b", 2, "generic_software")
    ],
    "NETWORK": [
        (r"\b(wi-?fi|wlan|wireless|ssid)\b", 4, "wifi_network"),
        (r"\b(vpn|virtual\s*private\s*network|tunnel|openvpn)\b", 5, "vpn_network"),
        (r"\b(ethernet|lan|rj45|cat6|switch|router)\b", 4, "ethernet_hardware"),
        (r"\b(dns|ip\s*address|subnet|gateway|dhcp)\b", 4, "network_config"),
        (r"\b(internet|no\s*internet|disconnect(ed|ion)?|offline)\b", 4, "internet_connectivity"),
        (r"\b(ping|latency|packet\s*loss|lag|high\s*jitter)\b", 4, "network_performance"),
        (r"\b(firewall|proxy|blocked\s*port|ssl\s*handshake)\b", 4, "network_security"),
        (r"\b(slow\s*browsing|unable\s*to\s*connect|connection\s*timed\s*out)\b", 4, "connection_failure"),
        (r"\b(bandwidth|isp|speed\s*test|slow\s*network)\b", 3, "bandwidth_issue")
    ],
    "ACCESS_SECURITY": [
        (r"\b(password\s*(reset|expired|forgotten|change)?)\b", 5, "password_issue"),
        (r"\b(login|log\s*in|sign\s*in|sso|single\s*sign\s*on)\b", 4, "authentication"),
        (r"\b(2fa|mfa|two\s*factor|otp|authenticator|token)\b", 5, "multi_factor_auth"),
        (r"\b(permission(s)?|access\s*(denied|requested|forbidden)|privilege(s)?)\b", 5, "access_control"),
        (r"\b(badge|keycard|security\s*clearance|biometric)\b", 4, "physical_security"),
        (r"\b(lockout|account\s*locked|unlocked\s*account)\b", 5, "account_lockout"),
        (r"\b(credentials|unauthorized|phishing|malware|suspicious\s*email)\b", 5, "security_threat"),
        (r"\b(role|admin\s*access|sudo|root\s*permission)\b", 4, "elevated_permissions")
    ],
    "BILLING_ACCOUNT": [
        (r"\b(invoice|receipt|statement|purchase\s*order|po\b)\b", 5, "invoice_billing"),
        (r"\b(payment|charge(d|s)?|credit\s*card|debit|bank\s*transfer)\b", 5, "payment_processing"),
        (r"\b(subscription|renewal|plan\s*(upgrade|downgrade)|tier)\b", 4, "subscription_management"),
        (r"\b(refund|overcharge(d)?|reimbursement|billing\s*dispute)\b", 5, "refund_dispute"),
        (r"\b(pricing|quote|cost|license\s*fee|rate)\b", 3, "pricing_query"),
        (r"\b(expense|payroll|compensation|financial\s*account)\b", 4, "financial_account"),
        (r"\b(tax|vat|gst|currency|wire\s*transfer)\b", 3, "tax_currency")
    ]
}

# Compile patterns for efficiency
COMPILED_PATTERNS = {
    cat: [
        (re.compile(pat, re.IGNORECASE), weight, label)
        for pat, weight, label in patterns
    ]
    for cat, patterns in REGEX_PATTERNS.items()
}

def classify_text_regex(text: str) -> Dict[str, Any]:
    """
    Independent Regex Classification Engine.
    Matches weighted regular expressions and calculates score distribution.
    """
    start_time = time.perf_counter()
    scores: Dict[str, int] = {cat: 0 for cat in COMPILED_PATTERNS}
    matched_patterns: List[Dict[str, Any]] = []

    for cat, patterns in COMPILED_PATTERNS.items():
        for regex, weight, label in patterns:
            matches = list(regex.finditer(text))
            if matches:
                # Add score weighted by matches
                match_count = len(matches)
                total_pattern_score = weight * match_count
                scores[cat] += total_pattern_score
                
                matched_patterns.append({
                    "category": cat,
                    "label": label,
                    "pattern": regex.pattern,
                    "matches": [m.group(0) for m in matches],
                    "weight": weight,
                    "score": total_pattern_score
                })

    total_score = sum(scores.values())
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    if total_score == 0:
        return {
            "category": "HARDWARE",
            "confidence": 0.20,
            "is_fallback": True,
            "category_scores": scores,
            "matched_patterns": [],
            "total_score": 0,
            "execution_time_ms": elapsed_ms,
            "engine": "REGEX"
        }

    best_category = max(scores, key=scores.get)
    confidence = round(scores[best_category] / total_score, 3)

    return {
        "category": best_category,
        "confidence": max(confidence, 0.60),
        "is_fallback": False,
        "category_scores": scores,
        "matched_patterns": matched_patterns,
        "total_score": total_score,
        "execution_time_ms": elapsed_ms,
        "engine": "REGEX"
    }
