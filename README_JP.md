# Discord Permission Auditor

軽量なDiscord Botです。サーバーの権限設定やセキュリティリスクをスキャンし、**初心者にもわかりやすく**報告します。

バックグラウンドタスク・データベース・外部APIは一切使用しません。  
スラッシュコマンドを実行したときだけ動作するため、メモリとCPU使用量を最小限に抑えられます。

---

## 機能

- 🔍 **総合監査** – `@everyone`、Bot、ロール、チャンネル、招待、Webhookなどをチェック
- 🛡️ **リスク評価** – Raid / Nuke / 外部攻撃 の3つのリスクを算出
- 📋 **わかりやすい説明** – 各問題に「何が悪いか」「なぜ危険か」「どう直すか」を表示
- 🔧 **ワンクリック修正** – 多くの問題を管理者がボタン一つで安全に修正可能
- 📄 **コピー用テキストレポート** – プレーンテキストで結果を簡単に共有・保存
- ⚙️ **設定可能** – JSONファイルでチェックのON/OFFやホワイトリストを指定
- 🚀 **軽量** – DB不要、常駐処理なし、外部APIなし

---

## セットアップ

Python 3.10+ が必要です。

```
python -m venv .venv
source .venv/bin/activate   # Windowsの場合: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` を編集して以下を設定します：

| 変数 | 説明 |
|------|------|
| `DISCORD_TOKEN` | Discord Developer Portal で取得したBotトークン。**必須** |
| `GUILD_ID` | コマンドを同期するサーバーID。任意（省略時はグローバル） |
| `CONFIG_FILE` | オプションのJSON設定ファイルへのパス。任意 |

Botには最低限以下の権限を付与してください：

- 監査ログを表示
- ロールの管理（ロール階層の正確な読み取り用）
- メッセージを読む / チャンネルを見る
- Webhookの管理（Webhookチェック用）
- サーバーの管理（招待チェック用）

起動：

```
python main.py
```

---

## コマンド

全コマンドは **管理者限定** で、応答は **Ephemeral（実行者のみ閲覧可能）** です。

| コマンド | 説明 |
|----------|------|
| `/audit` | 全チェックを実行 – リスクサマリー・詳細・修正ボタンを表示 |
| `/audit-channel` | `@everyone` が読めるチャンネルを一覧表示 |
| `/audit-mention` | `@everyone` / `@here` をメンションできる非管理者メンバーを一覧表示 |
| `/audit-help` | チェック一覧と設定方法を表示 |
| `/fix` | 自動修正可能な問題を選択して修正 |

---

## リスク評価

`/audit` 実行時、以下の3つのリスクレベルを算出します：

| リスク | 意味 |
|--------|------|
| **Raidリスク** | 大量参加攻撃やスパムに対する脆弱性 |
| **Nukeリスク** | 悪意のあるユーザー/Botがチャンネル・ロール・設定を破壊する容易さ |
| **外部攻撃リスク** | 新規メンバーや未信頼メンバーからの脅威に対する露出度 |

各リスクは `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO` で評価されます。

---

## オプション設定ファイル

`.env` に `CONFIG_FILE=config.json` を設定すると、JSON設定ファイルが使用できます。

例：

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
  "whitelist_roles": ["スタッフ", "123456789012345678"],
  "whitelist_channels": ["秘密ログ", "987654321098765432"],
  "whitelist_bots": ["信頼できるBot", "111222333444555666"]
}
```

- `enabled` – 実行するチェックIDのリスト。省略すると全チェック実行
- `whitelist_*` – 監査対象外にするロール・チャンネル・BotのIDまたは名前

利用可能なチェックID：

| ID | 説明 |
|----|------|
| `everyone_excess` | `@everyone` の危険な権限 |
| `server_misconfig` | 2FA・認証レベル・招待/Webhook作成設定 |
| `role_inheritance` | ロール階層による冗長・漏洩権限 |
| `external_bot_usable` | 一般メンバーがユーザーインストールBot/外部アプリを公開使用できる設定 |
| `everyone_visible` | `@everyone` が読めるチャンネル |
| `mention_everyone` | `@everyone` / `@here` メンションできる非管理者メンバー |
| `stale_invites` | 期限切れしない招待リンク |
| `owner_admin_roles` | サーバーオーナー以外の管理者ロール保持者 |
| `integration_webhooks` | 作成者が退去した孤立Webhook |

---

## 自動修正

`/audit` 実行時、修正可能な問題には **🔧 修正** ボタンが表示されます。

ボタンをクリックすると確認モーダルが開き、具体的な変更内容が表示されます。  
確認後、Botが修正を適用し、再監査を提案します。

**現在修正可能な問題：**

- `@everyone` から危険な権限を削除
- `@everyone` の招待作成権限を無効化
- `@everyone` のWebhook管理権限を無効化
- 下位ロールから冗長な権限を削除
- `@everyone` のチャンネル可視性を制限
- 非管理者ロールから `@everyone` / `@here` メンション権限を削除
- ユーザーインストールBot/外部アプリの公開使用権限をロールまたはチャンネルから削除
- 期限切れしない招待リンクを削除
- 孤立したWebhookを削除

> ⚠️ Botは **ユーザーの明示的な確認なしに** 変更を実行することはありません。

---

## 重大度レベル

問題は以下の5段階で分類されます：

`CRITICAL > HIGH > MEDIUM > LOW > INFO`

サマリーEmbedの色は、検出された最悪の重大度を反映します。

---

## アーキテクチャ

```
main.py          → エントリーポイント、Cogを読み込み
cogs/
  ├── audit.py   → /audit, /audit-channel, /audit-mention
  ├── help.py    → /audit-help
  └── fix.py     → 修正ボタンと /fix
auditor.py       → 監査ロジックと修正関数
findings.py      → Findingデータモデル、Embed/テキストレポート生成
risks.py         → リスクスコア計算
config.py        → .env と JSON設定読み込み
```

---

## ライセンス

MIT License. 詳細は [LICENSE](LICENSE) を参照。
