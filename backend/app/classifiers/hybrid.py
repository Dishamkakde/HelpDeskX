import time
import re
from typing import Dict, Any
from .dfa_engine import classify_text_dfa
from .regex_engine import classify_text_regex

URGENCY_REGEX = {
    "CRITICAL": re.compile(r"\b(urgent|critical|immediately|emergency|system\s*down|production\s*outage|fire|smoke|data\s*loss|breach|exploit)\b", re.IGNORECASE),
    "HIGH": re.compile(r"\b(blocked|cannot\s*work|high\s*priority|asap|deadline|failing|severe|unusable|lockout)\b", re.IGNORECASE),
    "MEDIUM": re.compile(r"\b(issue|slow|intermittent|problem|bug|glitch|help|error|warning)\b", re.IGNORECASE),
    "LOW": re.compile(r"\b(request|inquiry|question|when\s*possible|feature|how\s*to|minor|cosmetic)\b", re.IGNORECASE)
}

def infer_priority(text: str) -> str:
    for priority, pattern in URGENCY_REGEX.items():
        if pattern.search(text):
            return priority
    return "MEDIUM"

def classify_text_hybrid(text: str) -> Dict[str, Any]:
    """
    Executes both DFA and Regex engines independently, performs arbitration,
    and returns a comprehensive classification result.
    """
    start_time = time.perf_counter()
    
    dfa_res = classify_text_dfa(text)
    regex_res = classify_text_regex(text)
    
    dfa_cat = dfa_res["category"]
    regex_cat = regex_res["category"]
    is_agreement = (dfa_cat == regex_cat) and not (dfa_res["is_fallback"] and regex_res["is_fallback"])

    # Arbitration logic
    if is_agreement:
        final_category = dfa_cat
        # Boost confidence when both engines independently agree
        final_confidence = min(round((dfa_res["confidence"] + regex_res["confidence"]) / 1.8, 3), 0.99)
        arbitration_note = "Complete agreement between DFA and Regex engines."
    elif not regex_res["is_fallback"] and dfa_res["is_fallback"]:
        final_category = regex_cat
        final_confidence = regex_res["confidence"]
        arbitration_note = "Regex matched phrase patterns while DFA was inconclusive."
    elif not dfa_res["is_fallback"] and regex_res["is_fallback"]:
        final_category = dfa_cat
        final_confidence = dfa_res["confidence"]
        arbitration_note = "DFA matched lexical tokens while Regex patterns were inconclusive."
    elif not dfa_res["is_fallback"] and not regex_res["is_fallback"]:
        # Both matched different categories; compare confidence
        if regex_res["confidence"] >= dfa_res["confidence"]:
            final_category = regex_cat
            final_confidence = regex_res["confidence"]
            arbitration_note = f"Regex confidence ({regex_res['confidence']}) exceeded DFA confidence ({dfa_res['confidence']})."
        else:
            final_category = dfa_cat
            final_confidence = dfa_res["confidence"]
            arbitration_note = f"DFA confidence ({dfa_res['confidence']}) exceeded Regex confidence ({regex_res['confidence']})."
    else:
        # Both fell back
        final_category = "HARDWARE"
        final_confidence = 0.25
        arbitration_note = "No domain patterns recognized by either engine. Fallback to default queue."

    suggested_priority = infer_priority(text)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    return {
        "category": final_category,
        "confidence": final_confidence,
        "suggested_priority": suggested_priority,
        "engine_agreement": is_agreement,
        "arbitration_note": arbitration_note,
        "dfa_result": dfa_res,
        "regex_result": regex_res,
        "total_execution_time_ms": elapsed_ms,
        "engine": "HYBRID"
    }
