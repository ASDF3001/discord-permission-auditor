import discord
from discord import app_commands
from discord.ext import commands
import config
from auditor import check_everyone_visible, check_mention_everyone, run_audit
from findings import build_detail_embeds, build_summary_embed, build_text_report
from risks import calculate_risks
from cogs.fix import FixView  # 自動修正ボタンをインポート


class AuditCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="audit", description="Audit this server's permission gaps.")
    @app_commands.default_permissions(administrator=True)
    async def audit_all(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみ実行できます。", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        await interaction.response.send_message("スキャン中…少々お待ちください。", ephemeral=True)
        cfg = config.load_config()
        findings, ran = await run_audit(guild, cfg)
        risks = calculate_risks(findings)

        # サマリー（リスク情報付き）
        summary = build_summary_embed(guild.name, findings, ran, risks=risks)
        await interaction.followup.send(embed=summary)

        # テキストレポート（コピー用）
        text_report = build_text_report(guild.name, findings, risks)
        if len(text_report) <= 2000:
            await interaction.followup.send(f"```\n{text_report}\n```")
        else:
            await interaction.followup.send("テキストレポートが長すぎるため、詳細はEmbedをご覧ください。")

        # 詳細Embed（修正可能なものはボタン付きで表示）
        details = build_detail_embeds(findings)
        for emb in details:
            await interaction.followup.send(embed=emb)

        # ---- ここから自動修正ボタン ----
        # 修正可能なFindingだけを抽出（最大5件まで）
        fixable = [f for f in findings if f.auto_fixable][:5]

        if fixable:
            # 各Findingに個別の修正ボタンを作成
            view = discord.ui.View(timeout=120)

            for i, f in enumerate(fixable):
                # ボタンラベルは短く
                label = f"🔧 {f.title[:20]}"
                if len(f.title) > 20:
                    label += "…"

                # 各Finding専用のFixViewを埋め込む（カスタムIDで識別）
                button = discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.primary,
                    custom_id=f"fix_{i}_{f.check}"  # 一意にする
                )

                # ボタンのコールバックを動的に設定
                async def button_callback(interaction: discord.Interaction, f=f):
                    # FixViewを表示（モーダルを出す）
                    view = FixView(f, guild, self)
                    await interaction.response.send_message(
                        f"**{f.title}** を修正しますか？\n"
                        "以下のボタンをクリックして確認画面に進んでください。",
                        view=view,
                        ephemeral=True
                    )

                button.callback = button_callback
                view.add_item(button)

            # 件数が多い場合の案内
            total_fixable = len([f for f in findings if f.auto_fixable])
            footer_text = f"修正可能な問題: {total_fixable}件中 {len(fixable)}件を表示"
            if total_fixable > 5:
                footer_text += "（残りは /audit-fix コマンドで）"

            await interaction.followup.send(
                f"🔧 **自動修正可能な問題があります**\n"
                f"{footer_text}\n"
                "ボタンをクリックして修正を開始してください。",
                view=view,
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "✅ 自動修正可能な問題はありません。",
                ephemeral=True
            )

    @app_commands.command(name="audit-channel", description="List channels @everyone can read.")
    @app_commands.default_permissions(administrator=True)
    async def audit_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみ実行できます。", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        cfg = config.load_config()
        findings: list = []
        await check_everyone_visible(guild, cfg, findings)
        if not findings:
            await interaction.followup.send("公開チャンネルは見つかりませんでした（または全て非表示です）。")
            return
        for emb in build_detail_embeds(findings):
            await interaction.followup.send(embed=emb)

    @app_commands.command(name="audit-mention", description="List members who can mention @everyone/@here.")
    @app_commands.default_permissions(administrator=True)
    async def audit_mention(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみ実行できます。", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        cfg = config.load_config()
        findings: list = []
        await check_mention_everyone(guild, cfg, findings)
        if not findings:
            await interaction.followup.send("@everyone/@hereをメンションできる一般メンバーはいません。")
            return
        for emb in build_detail_embeds(findings):
            await interaction.followup.send(embed=emb)


async def setup(bot: commands.Bot):
    await bot.add_cog(AuditCog(bot))