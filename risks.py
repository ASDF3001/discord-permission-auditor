"""Risk assessment for Discord servers.

Calculates Raid, Nuke, and External Attack risks based on audit findings.
"""

from typing import List, Dict
from findings import Finding, Severity

# 各チェックタイプがどのリスクに影響するか
RISK_MAPPING = {
    "everyone_excess": {"raid": 3, "nuke": 2, "external": 3},
    "external_bot_perms": {"raid": 1, "nuke": 3, "external": 1},
    "server_misconfig": {"raid": 2, "nuke": 1, "external": 2},
    "role_inheritance": {"raid": 2, "nuke": 2, "external": 1},
    "external_bot_usable": {"raid": 2, "nuke": 1, "external": 1},
    "everyone_visible": {"raid": 1, "nuke": 0, "external": 2},
    "mention_everyone": {"raid": 3, "nuke": 1, "external": 2},
    "stale_invites": {"raid": 1, "nuke": 0, "external": 3},
    "owner_admin_roles": {"raid": 1, "nuke": 2, "external": 1},
    "integration_webhooks": {"raid": 1, "nuke": 2, "external": 1},
}

# Severityの重み
SEVERITY_WEIGHT = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.INFO: 0,
}

def calculate_risks(findings: List[Finding]) -> Dict[str, str]:
    """Calculate risk levels based on findings."""
    raid_score = 0
    nuke_score = 0
    external_score = 0

    for f in findings:
        if f.check in RISK_MAPPING:
            weight = SEVERITY_WEIGHT.get(f.severity, 1)
            mapping = RISK_MAPPING[f.check]
            raid_score += mapping.get("raid", 0) * weight
            nuke_score += mapping.get("nuke", 0) * weight
            external_score += mapping.get("external", 0) * weight

    return {
        "raid": _risk_level(raid_score),
        "nuke": _risk_level(nuke_score),
        "external": _risk_level(external_score),
    }

def _risk_level(score: int) -> str:
    if score >= 20:
        return "CRITICAL"
    elif score >= 12:
        return "HIGH"
    elif score >= 6:
        return "MEDIUM"
    elif score >= 2:
        return "LOW"
    else:
        return "INFO"