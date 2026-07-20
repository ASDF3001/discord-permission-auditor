"""Permission audit logic.

Each check is a standalone coroutine that appends Finding objects to a list.
Heavy lifting uses guild cache (guild.roles, guild.channels, guild.members)
to keep memory and API usage low; only invites fetch live data on demand.
"""

from typing import List

import discord

from findings import Finding, Severity

# Permissions considered dangerous when held by @everyone or external bots.
DANGEROUS_PERMS = {
    "administrator": Severity.CRITICAL,
    "ban_members": Severity.HIGH,
    "kick_members": Severity.HIGH,
    "manage_guild": Severity.HIGH,
    "manage_roles": Severity.HIGH,
    "manage_channels": Severity.HIGH,
    "manage_webhooks": Severity.MEDIUM,
    "manage_emojis": Severity.MEDIUM,
    "manage_nicknames": Severity.MEDIUM,
    "mention_everyone": Severity.MEDIUM,
    "manage_messages": Severity.HIGH,
    "moderate_members": Severity.HIGH,
}


def _perm_label(perm: str) -> str:
    return perm.replace("_", " ").title()


async def check_bot_self(guild: discord.Guild, me: discord.Member, out: List[Finding]) -> None:
    """Verify the bot can actually read what it needs. Not a gap in the server."""
    needed = [
        "view_audit_log",
        "manage_roles",   # to read high-position roles accurately
        "read_messages",
    ]
    missing = [p for p in needed if not getattr(me.guild_permissions, p, False)]
    if missing:
        out.append(
            Finding(
                severity=Severity.INFO,
                check="bot_perm_selfcheck",
                title="Bot permission limited",
                detail="Missing: " + ", ".join(_perm_label(p) for p in missing)
                + ". Results may be incomplete or inaccurate.",
                recommendation="Grant the bot these permissions (Audit Log + Manage Roles help most).",
            )
        )


async def check_everyone_excess(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    everyone = guild.default_role
    for perm, sev in DANGEROUS_PERMS.items():
        if getattr(everyone.permissions, perm, False):
            out.append(
                Finding(
                    severity=sev,
                    check="everyone_excess",
                    title="@everyone has dangerous permission",
                    detail=f"@everyone grants '{_perm_label(perm)}' to every member.",
                    target="@everyone",
                    recommendation="Remove this permission from @everyone; assign via specific roles instead.",
                )
            )


async def check_external_bot_perms(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    for member in guild.members:
        if not member.bot:
            continue
        if cfg.bot_ignored(member):
            continue
        # external = not owned by this guild's owner / not a managed integration we trust
        is_external = member.id != guild.owner_id
        for perm, sev in DANGEROUS_PERMS.items():
            if getattr(member.guild_permissions, perm, False):
                out.append(
                    Finding(
                        severity=sev if is_external else Severity.MEDIUM,
                        check="external_bot_perms",
                        title="Bot with dangerous permission",
                        detail=f"'{member.name}' holds '{_perm_label(perm)}'."
                        + ("" if is_external else " (owned by server owner)"),
                        target=member.name,
                        recommendation="Review whether this bot needs the permission; scope it down if possible.",
                    )
                )


async def check_server_misconfig(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    # 2FA requirement not enforced
    if guild.mfa_level == 0:
        out.append(
            Finding(
                severity=Severity.MEDIUM,
                check="server_misconfig",
                title="2FA not required",
                detail="Server does not require two-factor auth for moderators/admins.",
                recommendation="Enable 'Require 2FA' in Server Settings > Safety Setup.",
            )
        )
    # Open join with no verification level
    if guild.verification_level in (discord.VerificationLevel.none,):
        out.append(
            Finding(
                severity=Severity.LOW,
                check="server_misconfig",
                title="No verification gate",
                detail="Verification level is 'None'; new members get full send access immediately.",
                recommendation="Raise verification level to at least 'Low' or 'Medium'.",
            )
        )
    # Explicit content filter off
    if guild.explicit_content_filter == discord.ContentFilter.disabled:
        out.append(
            Finding(
                severity=Severity.LOW,
                check="server_misconfig",
                title="Explicit content filter disabled",
                detail="NSFW media from non-friends is not scanned.",
                recommendation="Set explicit content filter to 'All members' in Server Settings.",
            )
        )
    # Anyone can create invites (guild-level)
    if guild.default_role.permissions.create_instant_invite:
        out.append(
            Finding(
                severity=Severity.LOW,
                check="server_misconfig",
                title="@everyone can create invites",
                detail="@everyone has 'Create Invite'. Members can invite anyone at any time.",
                target="@everyone",
                recommendation="Disable 'Create Invite' on @everyone and grant per-role as needed.",
            )
        )
    # Anyone can manage webhooks (guild-level)
    if guild.default_role.permissions.manage_webhooks:
        out.append(
            Finding(
                severity=Severity.HIGH,
                check="server_misconfig",
                title="@everyone can manage webhooks",
                detail="@everyone holds 'Manage Webhooks'. Any member can post as any webhook.",
                target="@everyone",
                recommendation="Remove 'Manage Webhooks' from @everyone.",
            )
        )


async def check_role_inheritance(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    """Detect roles that grant a dangerous perm but sit below a role whose
    members could inherit it unintentionally via hoist/position overlap."""
    sorted_roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
    for role in sorted_roles:
        if cfg.role_ignored(role):
            continue
        if role.is_default():
            continue
        for perm, sev in DANGEROUS_PERMS.items():
            if getattr(role.permissions, perm, False):
                # if a higher role also grants it, lower role is redundant
                higher_redundant = any(
                    (r.position > role.position and getattr(r.permissions, perm, False))
                    for r in sorted_roles
                )
                if higher_redundant:
                    out.append(
                        Finding(
                            severity=Severity.LOW,
                            check="role_inheritance",
                            title="Redundant dangerous permission",
                            detail=f"Role '{role.name}' grants '{_perm_label(perm)}' "
                            "but a higher role already grants it.",
                            target=role.name,
                            recommendation="Drop the permission from the lower role to reduce blast radius.",
                        )
                    )


async def check_external_bot_usable(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    """External bot is usable by @everyone if @everyone can 'Use Application Commands'
    (guild default) and the bot's role is below @everyone hierarchy issues... we flag
    bots whose integration role is lower than some member roles but still usable."""
    if not guild.default_role.permissions.use_application_commands:
        return  # @everyone cannot use app commands at all
    for member in guild.members:
        if not member.bot or member.id == guild.owner_id:
            continue
        if cfg.bot_ignored(member):
            continue
        # a bot is "usable by everyone" when no channel denies Use Application Commands
        # to it specifically (i.e. it is not confined to specific channels/roles).
        confined = any(
            ch.permissions_for(member).use_application_commands is False
            for ch in guild.channels
        )
        if not confined:
            out.append(
                Finding(
                    severity=Severity.LOW,
                    check="external_bot_usable",
                    title="External bot usable by everyone",
                    detail=f"'{member.name}' can be invoked by any member (no command restriction).",
                    target=member.name,
                    recommendation="Restrict the bot to specific roles/channels if it should not be public.",
                )
            )


async def check_everyone_visible(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    visible = []
    for channel in guild.channels:
        if cfg.channel_ignored(channel):
            continue
        if isinstance(channel, (discord.CategoryChannel,)):
            continue
        perms = channel.permissions_for(guild.default_role)
        if perms.read_messages or perms.view_channel:
            name = getattr(channel, "name", str(channel))
            visible.append(f"#{name}")
    if visible:
        out.append(
            Finding(
                severity=Severity.INFO,
                check="everyone_visible",
                title="@everyone can read channels",
                detail="Readable by @everyone (" + str(len(visible)) + "): "
                + ", ".join(visible[:40])
                + (" ..." if len(visible) > 40 else ""),
                target="@everyone",
                recommendation="Confirm none of these should be staff/secret-only.",
            )
        )


async def check_mention_everyone(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    allowed = []
    for member in guild.members:
        if member.bot:
            continue
        # skip members whose highest role is administrator-equivalent
        if member.guild_permissions.administrator:
            continue
        if member.guild_permissions.mention_everyone:
            name = getattr(member, "display_name", member.name)
            allowed.append(name)
    if allowed:
        out.append(
            Finding(
                severity=Severity.INFO,
                check="mention_everyone",
                title="Members can mention @everyone / @here",
                detail=str(len(allowed)) + " non-admin member(s): "
                + ", ".join(allowed[:40])
                + (" ..." if len(allowed) > 40 else ""),
                recommendation="Remove 'Mention Everyone' from non-admin roles if pings should be limited.",
            )
        )


async def check_stale_invites(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    if not guild.me or not guild.me.guild_permissions.manage_guild:
        return
    try:
        invites = await guild.invites()
    except discord.Forbidden:
        return
    for inv in invites:
        if inv.max_age == 0:  # never expires
            out.append(
                Finding(
                    severity=Severity.LOW,
                    check="stale_invites",
                    title="Permanent invite exists",
                    detail=f"Invite {inv.code} never expires"
                    + (f" (made by {inv.inviter})" if inv.inviter else "")
                    + f", used {inv.uses} time(s).",
                    target=inv.code,
                    recommendation="Set an expiry or revoke if no longer needed.",
                )
            )


async def check_owner_admin_roles(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    """Members in admin-equivalent roles who are not the owner."""
    for role in guild.roles:
        if cfg.role_ignored(role):
            continue
        if not role.permissions.administrator:
            continue
        for member in role.members:
            if member.id == guild.owner_id or member.bot:
                continue
            out.append(
                Finding(
                    severity=Severity.HIGH,
                    check="owner_admin_roles",
                    title="Non-owner with admin role",
                    detail=f"'{getattr(member, 'display_name', member.name)}' has role '{role.name}' "
                    "which grants Administrator.",
                    target=member.name,
                    recommendation="Confirm this person should have full server control; limit admin roles.",
                )
            )


async def check_integration_webhooks(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    if not guild.me or not guild.me.guild_permissions.manage_webhooks:
        return
    try:
        hooks = await guild.webhooks()
    except discord.Forbidden:
        return
    bot_ids = {m.id for m in guild.members if m.bot}
    for hook in hooks:
        # webhook whose creator is no longer in the server (user_id missing) or unknown
        creator_gone = hook.user is None or (hook.user.id not in bot_ids and hook.user.id not in {m.id for m in guild.members})
        if creator_gone:
            out.append(
                Finding(
                    severity=Severity.MEDIUM,
                    check="integration_webhooks",
                    title="Orphaned webhook",
                    detail=f"Webhook '{hook.name}' in <#{hook.channel_id}> has no visible creator.",
                    target=hook.name or "unknown",
                    recommendation="Remove webhooks left by departed bots/members.",
                )
            )


# Ordered registry used by the runner.
ALL_CHECKS = [
    ("bot_perm_selfcheck", check_bot_self),
    ("everyone_excess", check_everyone_excess),
    ("external_bot_perms", check_external_bot_perms),
    ("server_misconfig", check_server_misconfig),
    ("role_inheritance", check_role_inheritance),
    ("external_bot_usable", check_external_bot_usable),
    ("everyone_visible", check_everyone_visible),
    ("mention_everyone", check_mention_everyone),
    ("stale_invites", check_stale_invites),
    ("owner_admin_roles", check_owner_admin_roles),
    ("integration_webhooks", check_integration_webhooks),
]


async def run_audit(guild: discord.Guild, cfg) -> tuple[List[Finding], int]:
    """Run all enabled checks. Returns (findings, number_of_checks_run)."""
    out: List[Finding] = []
    me = guild.me
    ran = 0
    for check_id, fn in ALL_CHECKS:
        if not cfg.is_enabled(check_id):
            continue
        ran += 1
        try:
            if check_id == "bot_perm_selfcheck":
                await fn(guild, me, out)
            else:
                await fn(guild, cfg, out)
        except discord.Forbidden:
            # missing a specific permission for this check; record once
            out.append(
                Finding(
                    severity=Severity.INFO,
                    check=check_id,
                    title="Check skipped",
                    detail=f"Bot lacks permission to read data for '{check_id}'.",
                    recommendation="Grant the bot broader read access to include this check.",
                )
            )
        except Exception:  # noqa: BLE001 - never let one check kill the run
            continue
    return out, ran
