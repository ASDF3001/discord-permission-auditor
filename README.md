# Discord Permission Auditor

日本語版:[README_JP](README_JP.md)
A small, dependency-light Discord bot that scans a server for permission gaps
and misconfigurations, then reports them in Discord with a severity rating.

No background tasks, no database, no external calls. It runs only when you
invoke a slash command, so memory and CPU use stay minimal.

## Features

- Scans for dangerous permissions on `@everyone` and external bots
- Flags server misconfigurations (2FA, verification, webhook/invite creation)
- Detects redundant or leaked permissions through role inheritance
- Lists channels readable by `@everyone`
- Lists non-admin members who can mention `@everyone` / `@here`
- Surfaces stale invites and orphaned webhooks
- Per-check toggles and whitelists via a JSON config file
- Plain output, no emoji

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

| Variable      | Description                                                        |
|---------------|--------------------------------------------------------------------|
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal. **Required.**       |
| `GUILD_ID`      | Server ID to sync commands to. Optional; without it, commands are global. |
| `CONFIG_FILE`   | Path to an optional JSON config (toggles + whitelist). Optional.   |

Invite the bot with at least these permissions:

- View Audit Log
- Manage Roles (helps read high-position roles accurately)
- Read Messages / View Channels
- Manage Webhooks (for the webhook check)
- Manage Server (for the invite check)

Then run:

```bash
python bot.py
```

## Commands

| Command            | What it does                                              |
|--------------------|-----------------------------------------------------------|
| `/audit`           | Run all enabled checks on the current server.             |
| `/audit-channel`   | List channels `@everyone` can read.                       |
| `/audit-mention`   | List non-admin members who can mention `@everyone`/`@here`. |
| `/audit-help`      | Show the check list and configuration notes.              |

## Optional config file

Set `CONFIG_FILE=config.json` in `.env`. Example:

```json
{
  "enabled": [
    "everyone_excess",
    "external_bot_perms",
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

- `enabled`: subset of check ids to run. Omit the key to run all.
- `whitelist_*`: role / channel / bot ids or names to ignore.

## Severity levels

`CRITICAL > HIGH > MEDIUM > LOW > INFO`. The summary embed color reflects the
worst issue found.

## License

MIT. See [LICENSE](LICENSE).
