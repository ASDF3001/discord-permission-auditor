# Discord Permission Auditor

バックグラウンドタスク、データベース、外部通信は一切使用しません。  
スラッシュコマンドを実行したときだけ監査を行うため、メモリとCPU使用量を最小限に抑えられます。

## Features

- `@everyone` や外部Botが持つ危険な権限を検出
- サーバー設定の問題を検出
  - 2FA
  - 認証レベル
  - Webhook作成
  - 招待作成
- ロール継承による冗長な権限・権限漏れを検出
- `@everyone` が閲覧できるチャンネルを一覧表示
- 管理者権限を持たないメンバーのうち、`@everyone` / `@here` をメンションできるユーザーを検出
- 古い招待リンクを検出
- 孤立したWebhookを検出
- JSON設定ファイルによるチェック項目の個別有効化・無効化
- ロール・チャンネル・Botのホワイトリストに対応
- 検出結果を重大度別に分類

## Setup

### Requirements

- Python 3.10+
- Discord Bot

### Installation

```bash
python -m venv .venv
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\activate
```

依存関係をインストールします。

```bash
pip install -r requirements.txt
```

`.env.example` をコピーして `.env` を作成します。

```bash
cp .env.example .env
```

Windowsの場合は、`.env.example` をコピーして `.env` を作成してください。

### Environment Variables

`.env` に以下を設定します。

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Discord Developer Portalで取得したBotトークン。必須 |
| `GUILD_ID` | スラッシュコマンドを同期するサーバーID。任意 |
| `CONFIG_FILE` | 任意のJSON設定ファイルへのパス。任意 |

`GUILD_ID` を指定しない場合、コマンドはグローバルコマンドとして登録されます。

## Bot Permissions

Botには最低限、以下の権限を付与してください。

- View Audit Log
- Manage Roles
- Read Messages / View Channels
- Manage Webhooks
- Manage Server

`Manage Roles` は、ロールの順位や権限継承を正確に確認するために使用します。

`Manage Webhooks` はWebhook監査に、`Manage Server` は招待監査に使用します。

## Run

```bash
python bot.py
```

## Commands

| Command | Description |
|---|---|
| `/audit` | 有効になっているすべての監査項目を実行 |
| `/audit-channel` | `@everyone` が閲覧できるチャンネルを一覧表示 |
| `/audit-mention` | `@everyone` / `@here` をメンションできる非管理者メンバーを一覧表示 |
| `/audit-help` | 監査項目と設定方法を表示 |

## Configuration

`.env` に以下を設定すると、JSON設定ファイルを使用できます。

```env
CONFIG_FILE=config.json
```

### Example

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
  "whitelist_roles": [
    "Staff",
    "123456789012345678"
  ],
  "whitelist_channels": [
    "secret-logs",
    "987654321098765432"
  ],
  "whitelist_bots": [
    "TrustedBot",
    "111222333444555666"
  ]
}
```

### `enabled`

実行する監査項目を指定します。

| Check ID | Description |
|---|---|
| `everyone_excess` | `@everyone` の危険な権限 |
| `external_bot_perms` | 外部Botの危険な権限 |
| `server_misconfig` | サーバー設定の問題 |
| `role_inheritance` | ロール継承による権限問題 |
| `external_bot_usable` | 外部Botの実効権限 |
| `everyone_visible` | `@everyone` が閲覧できるチャンネル |
| `mention_everyone` | `@everyone` / `@here` メンション権限 |
| `stale_invites` | 古い招待リンク |
| `owner_admin_roles` | サーバー所有者・管理者ロールの確認 |
| `integration_webhooks` | Webhook関連の問題 |

`enabled` を省略した場合、すべての監査項目が実行されます。

### Whitelists

特定のロール、チャンネル、Botを監査対象から除外できます。

#### `whitelist_roles`

ロール名またはロールIDを指定します。

#### `whitelist_channels`

チャンネル名またはチャンネルIDを指定します。

#### `whitelist_bots`

Bot名またはBot IDを指定します。

## Severity Levels

監査結果は以下の5段階で分類されます。

```text
CRITICAL > HIGH > MEDIUM > LOW > INFO
```

サマリーには、検出された中で最も高い重大度が反映されます。

## Design Philosophy

このBotは、Discordサーバーの権限設定を**監査・可視化すること**を目的としています。

権限を自動的に変更するのではなく、問題を検出して管理者に知らせることを基本方針としています。

### Principles

- Background tasksなし
- Databaseなし
- External APIへの通信なし
- 監査はコマンド実行時のみ
- 設定はローカルのJSONファイル
- 権限変更を自動実行しない
- 軽量な動作
- 明確な重大度表示

「危険な権限がある」という結果だけではなく、

- どの権限なのか
- 誰が持っているのか
- どのロールから継承されているのか
- なぜ問題なのか

を確認できることを重視しています。

## License

MIT License

詳細は `LICENSE` を参照してください。