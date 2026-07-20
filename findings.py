"""Findings: severity model, the Finding data class, and Discord embed rendering.

No emoji, no marketing copy. Plain, scannable output.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

import discord

# Embed accent colors per severity (Discord decimal format).
SEVERITY_COLOR = {
    "CRITICAL": 0x8B0000,  # dark red
    "HIGH": 0xC0392B,      # red
    "MEDIUM": 0xB9770E,    # amber
    "LOW": 0x1F618D,       # blue
    "INFO": 0x566573,      # grey
}


class Severity(IntEnum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    INFO = 0


@dataclass
class Finding:
    severity: Severity
    check: str          # check id, e.g. "everyone_excess"
    title: str          # short label
    detail: str         # what was found
    target: str = ""    # role / channel / member name
    recommendation: str = ""

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.name,
            "check": self.check,
            "title": self.title,
            "detail": self.detail,
            "target": self.target,
            "recommendation": self.recommendation,
        }


def sort_findings(findings: List[Finding]) -> List[Finding]:
    return sorted(findings, key=lambda f: f.severity.value, reverse=True)


def build_summary_embed(guild_name: str, findings: List[Finding], scanned: int) -> discord.Embed:
    counts = {s.name: 0 for s in Severity}
    for f in findings:
        counts[f.severity.name] += 1

    total = len(findings)
    if total == 0:
        color = 0x1E8449  # green
        desc = "No permission gaps detected in the enabled checks."
    else:
        # color follows the worst severity present
        worst = max(findings, key=lambda f: f.severity.value).severity
        color = SEVERITY_COLOR[worst.name]
        parts = [f"{name}: {counts[name]}" for name in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] if counts[name]]
        desc = f"{total} issue(s) found. " + " / ".join(parts)

    embed = discord.Embed(
        title=f"Permission audit - {guild_name}",
        description=desc,
        color=color,
    )
    embed.set_footer(text=f"Checks run: {scanned}")
    return embed


def build_detail_embeds(findings: List[Finding], per_embed: int = 25) -> List[discord.Embed]:
    """Split findings into multiple embeds (Discord field limits)."""
    embeds: List[discord.Embed] = []
    chunk = sort_findings(findings)
    for i in range(0, len(chunk), per_embed):
        group = chunk[i : i + per_embed]
        embed = discord.Embed(title="Audit details", color=SEVERITY_COLOR["INFO"])
        for f in group:
            name = f"[{f.severity.name}] {f.title}"
            if f.target:
                name += f" - {f.target}"
            body = f.detail
            if f.recommendation:
                body += f"\nFix: {f.recommendation}"
            embed.add_field(name=name[:256], value=body[:1024], inline=False)
        if len(chunk) > per_embed:
            embed.set_footer(text=f"Page {i // per_embed + 1}/{(len(chunk) - 1) // per_embed + 1}")
        embeds.append(embed)
    return embeds
