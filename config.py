"""Configuration loading for the permission auditor.

Reads the bot token and guild id from environment (.env), and an optional
JSON config file that controls which audit checks run and what is whitelisted
so intentional setups are not flagged as gaps.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID_RAW = os.getenv("GUILD_ID", "").strip()
CONFIG_FILE = os.getenv("CONFIG_FILE", "").strip()

GUILD_ID = int(GUILD_ID_RAW) if GUILD_ID_RAW.isdigit() else None


# Check identifiers. Used for on/off toggles and help text.
CHECK_IDS = [
    "everyone_excess",      # @everyone with dangerous permissions
    "server_misconfig",     # 2FA, join settings, webhook creation, nsfw
    "role_inheritance",     # overlapping / inherited permission leaks
    "external_bot_usable",  # user-installed/external apps usable publicly
    "everyone_visible",     # channels @everyone can read
    "mention_everyone",     # members allowed to mention @everyone/@here
    "bot_perm_selfcheck",   # bot's own permission sufficiency
    "stale_invites",        # never-expire invites / vanity abuse
    "owner_admin_roles",    # non-owner members in admin-equivalent roles
    "integration_webhooks", # webhooks from removed/unknown integrations
]


@dataclass
class GuildConfig:
    enabled: set = field(default_factory=lambda: set(CHECK_IDS))
    whitelist_roles: set = field(default_factory=set)   # role ids/names to ignore
    whitelist_channels: set = field(default_factory=set)  # channel ids/names to ignore
    whitelist_bots: set = field(default_factory=set)     # bot user ids/names to ignore

    def is_enabled(self, check_id: str) -> bool:
        return check_id in self.enabled

    def role_ignored(self, role) -> bool:
        return str(role.id) in self.whitelist_roles or role.name in self.whitelist_roles

    def channel_ignored(self, channel) -> bool:
        return str(channel.id) in self.whitelist_channels or channel.name in self.whitelist_channels

    def bot_ignored(self, member) -> bool:
        return str(member.id) in self.whitelist_bots or member.name in self.whitelist_bots


_DEFAULT = GuildConfig()


def _coerce_ids(values) -> set:
    out = set()
    for v in values or []:
        out.add(str(v))
    return out


def load_config() -> GuildConfig:
    """Load optional JSON config. Falls back to all-checks-enabled defaults."""
    if not CONFIG_FILE:
        return _DEFAULT
    path = Path(CONFIG_FILE)
    if not path.is_file():
        return _DEFAULT
    try:
        with path.open(encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return _DEFAULT

    enabled_raw = data.get("enabled")
    if enabled_raw is None:
        enabled = set(CHECK_IDS)
    else:
        enabled = {c for c in CHECK_IDS if c in enabled_raw}

    return GuildConfig(
        enabled=enabled,
        whitelist_roles=_coerce_ids(data.get("whitelist_roles")),
        whitelist_channels=_coerce_ids(data.get("whitelist_channels")),
        whitelist_bots=_coerce_ids(data.get("whitelist_bots")),
    )
