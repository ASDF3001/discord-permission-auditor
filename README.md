# Discord Permission Auditor

A lightweight Discord bot that scans your server for permission gaps, security misconfigurations, and risks.  
Designed for server admins who want clear, actionable reports — not just raw permissions.

日本語版: [README_JP.md](README_JP.md)

---

## Features

- 🔍 **Comprehensive audit** – checks `@everyone`, bots, roles, channels, invites, webhooks, and more
- 🛡️ **Risk scoring** – evaluates Raid, Nuke, and External Attack risks
- 📋 **Clear explanations** – each finding includes what's wrong, why it matters, and how to fix it
- 🔧 **One‑click fixes** – safely resolve many issues with a single button (admin only)
- 📄 **Copy‑ready text report** – plain text summary for easy sharing or saving
- ⚙️ **Configurable** – enable/disable checks, whitelist roles/channels/bots via JSON
- 🚀 **Lightweight** – no database, no background tasks, no external APIs

---

## Setup

Requires Python 3.10+.

```
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Bot token from Discord Developer Portal. **Required.** |
| `GUILD_ID` | Server ID to sync commands to. Optional (global if omitted). |
| `CONFIG_FILE` | Path to optional JSON config (toggles + whitelists). Optional. |

Invite the bot with at least these permissions:

- View Audit Log
- Manage Roles (for accurate role hierarchy reading)
- Read Messages / View Channels
- Manage Webhooks (for webhook checks)
- Manage Server (for invite checks)

Then run:

```
python main.py
```

---

## Commands

All commands are **administrator‑only** and respond **ephemerally** (only you can see the results).

| Command | Description |
|---------|-------------|
| `/audit` | Run all enabled checks – shows risk summary, detailed findings, and fix buttons. |
| `/audit-channel` | List channels `@everyone` can read. |
| `/audit-mention` | List non‑admin members who can mention `@everyone` / `@here`. |
| `/audit-help` | Show the check list and configuration notes. |
| `/fix` | Select and apply auto-fixable issues. |

---

## Risk Assessment

After each full audit, the bot calculates three risk levels:

| Risk | What it means |
|------|---------------|
| **Raid Risk** | How vulnerable the server is to mass‑join attacks and spam. |
| **Nuke Risk** | How easily a malicious user or bot could destroy channels, roles, and settings. |
| **External Attack Risk** | How exposed the server is to threats from new or untrusted members. |

Each risk is rated as `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO` based on the findings.

---

## Optional Config File

Set `CONFIG_FILE=config.json` in `.env`. Example:

```
{
  "enabled": [
    "everyone_excess",
    "server_misconfig",
    "role_inheritance",
    "external_bot_usable",
    "everyone_visible",
    "mention_everyone",
    "stale_invites",
    "owner_admin_roles",
    "integration_webhooks"
  ],
  "whitelist_roles": ["Staff", "123456789012345678"],
  "whitelist_channels": ["secret-logs", "987654321098765432"],
  "whitelist_bots": ["TrustedBot", "111222333444555666"]
}
```

- `enabled` – subset of check IDs to run. Omit to run all.
- `whitelist_*` – role / channel / bot IDs or names to ignore during audits.

Available check IDs:

| ID | Description |
|----|-------------|
| `everyone_excess` | Dangerous permissions on `@everyone` |
| `server_misconfig` | 2FA, verification, invite/webhook creation settings |
| `role_inheritance` | Redundant or leaked permissions via role hierarchy |
| `external_bot_usable` | User-installed/external apps can be used publicly by regular members |
| `everyone_visible` | Channels readable by `@everyone` |
| `mention_everyone` | Non‑admin members with `@everyone` / `@here` mention permission |
| `stale_invites` | Never‑expiring invites |
| `owner_admin_roles` | Non‑owner members with admin roles |
| `integration_webhooks` | Orphaned webhooks (creator left the server) |

---

## Auto‑Fix

When you run `/audit`, any fixable issues will appear with a **🔧 Fix** button.

Clicking the button opens a confirmation modal showing exactly what will be changed.  
After you confirm, the bot applies the fix and offers to re‑audit the server.

**Currently fixable issues:**

- Remove dangerous permissions from `@everyone`
- Disable invite creation on `@everyone`
- Disable webhook management on `@everyone`
- Remove redundant permissions from lower roles
- Restrict `@everyone` from viewing public channels
- Remove `@everyone` / `@here` mention permission from non‑admin roles
- Remove public user-installed/external app usage from roles or channel overwrites
- Delete never‑expiring invites
- Delete orphaned webhooks

> ⚠️ The bot **never** makes changes without your explicit confirmation.

---

## Severity Levels

Findings are classified as:

`CRITICAL > HIGH > MEDIUM > LOW > INFO`

The summary embed's color reflects the worst issue found.

---

## Architecture

```
main.py          → Bot entry point, loads cogs
cogs/
  ├── audit.py   → /audit, /audit-channel, /audit-mention
  ├── help.py    → /audit-help
  └── fix.py     → Fix buttons and /fix
auditor.py       → Core audit logic and fix functions
findings.py      → Finding data model, embed/text report builders
risks.py         → Risk score calculator
config.py        → .env and JSON config loader
```

---

## License

MIT. See [LICENSE](LICENSE).
