"""Findings: severity model, the Finding data class, and Discord embed rendering."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional
import discord

SEVERITY_COLOR = {
    "CRITICAL": 0x8B0000,
    "HIGH": 0xC0392B,
    "MEDIUM": 0xB9770E,
    "LOW": 0x1F618D,
    "INFO": 0x566573,
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
    check: str
    title: str
    detail: str
    target: str = ""
    recommendation: str = ""
    description: str = ""
    impact: str = ""
    fix_steps: List[str] = field(default_factory=list)
    auto_fixable: bool = False

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.name,
            "check": self.check,
            "title": self.title,
            "detail": self.detail,
            "target": self.target,
            "recommendation": self.recommendation,
            "description": self.description,
            "impact": self.impact,
            "fix_steps": self.fix_steps,
            "auto_fixable": self.auto_fixable,
        }


def sort_findings(findings: List[Finding]) -> List[Finding]:
    return sorted(findings, key=lambda f: f.severity.value, reverse=True)


def build_summary_embed(guild_name: str, findings: List[Finding], scanned: int, risks: dict = None) -> discord.Embed:
    counts = {s.name: 0 for s in Severity}
    for f in findings:
        counts[f.severity.name] += 1

    total = len(findings)
    if total == 0:
        color = 0x1E8449
        desc = "✅ 問題は検出されませんでした。このサーバーは安全です。"
    else:
        worst = max(findings, key=lambda f: f.severity.value).severity
        color = SEVERITY_COLOR[worst.name]
        parts = [f"{name}: {counts[name]}" for name in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] if counts[name]]
        desc = f"**{total}件**の問題が見つかりました。\n" + " / ".join(parts)

    embed = discord.Embed(
        title=f"🔒 権限監査レポート - {guild_name}",
        description=desc,
        color=color,
    )

    if risks:
        risk_text = (
            f"🛡️ **総合リスク評価**\n"
            f"・Raidリスク: {risks.get('raid', '不明')}\n"
            f"・Nukeリスク: {risks.get('nuke', '不明')}\n"
            f"・外部攻撃リスク: {risks.get('external', '不明')}"
        )
        embed.add_field(name="", value=risk_text, inline=False)

    embed.set_footer(text=f"実行したチェック数: {scanned}")
    return embed


def build_detail_embeds(findings: List[Finding], per_embed: int = 10) -> List[discord.Embed]:
    embeds: List[discord.Embed] = []
    chunk = sort_findings(findings)
    for i in range(0, len(chunk), per_embed):
        group = chunk[i: i + per_embed]
        embed = discord.Embed(title="📋 詳細レポート", color=SEVERITY_COLOR["INFO"])
        for f in group:
            name = f"**[{f.severity.name}] {f.title}**"
            if f.target:
                name += f" - {f.target}"

            body = f"**問題**: {f.description or f.detail}\n"
            if f.impact:
                body += f"**影響**: {f.impact}\n"
            if f.recommendation:
                body += f"**推奨**: {f.recommendation}\n"
            if f.fix_steps:
                body += "**修正手順**:\n" + "\n".join(f"  {i+1}. {step}" for i, step in enumerate(f.fix_steps[:3]))
            if f.auto_fixable:
                body += "\n✅ 自動修正可能"

            embed.add_field(name=name[:256], value=body[:1024], inline=False)
        if len(chunk) > per_embed:
            embed.set_footer(text=f"Page {i // per_embed + 1}/{(len(chunk) - 1) // per_embed + 1}")
        embeds.append(embed)
    return embeds


def build_text_report(guild_name: str, findings: List[Finding], risks: dict = None) -> str:
    lines = [
        "=" * 60,
        f"Discord セキュリティ監査レポート",
        f"サーバー: {guild_name}",
        "=" * 60,
        "",
        f"総問題数: {len(findings)}",
        "",
    ]

    if risks:
        lines.extend([
            "--- リスク評価 ---",
            f"Raidリスク: {risks.get('raid', '不明')}",
            f"Nukeリスク: {risks.get('nuke', '不明')}",
            f"外部攻撃リスク: {risks.get('external', '不明')}",
            "",
        ])

    if not findings:
        lines.append("✅ 問題は検出されませんでした。")
        return "\n".join(lines)

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        items = [f for f in sort_findings(findings) if f.severity.name == severity]
        if not items:
            continue
        lines.append(f"--- {severity} ({len(items)}件) ---")
        for f in items:
            lines.append(f"■ {f.title}")
            if f.target:
                lines.append(f"  対象: {f.target}")
            lines.append(f"  問題: {f.description or f.detail}")
            if f.impact:
                lines.append(f"  影響: {f.impact}")
            if f.recommendation:
                lines.append(f"  推奨: {f.recommendation}")
            if f.fix_steps:
                lines.append("  修正手順:")
                for i, step in enumerate(f.fix_steps, 1):
                    lines.append(f"    {i}. {step}")
            lines.append("")

    return "\n".join(lines)