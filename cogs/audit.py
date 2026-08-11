import discord
from discord import app_commands
from discord.ext import commands
import config
from auditor import check_everyone_visible, check_mention_everyone, run_audit
from findings import (
    build_detail_embeds,
    build_summary_embed,
    build_text_report,
    Severity,
)
from risks import calculate_risks
from cogs.fix import FixView


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

        summary = build_summary_embed(guild.name, findings, ran, risks=risks)
        await interaction.followup.send(embed=summary)

        # テキストレポートをtxtファイルで送信
        text_report = build_text_report(guild.name, findings, risks)
        if len(text_report) <= 2000:
            await interaction.followup.send(f"```\n{text_report}\n```")
        else:
            # テキストファイルとして送信
            file = discord.File(
                fp=discord.BytesIO(text_report.encode("utf-8")),
                filename="audit_report.txt",
            )
            await interaction.followup.send(file=file)

        details = build_detail_embeds(findings)
        for emb in details:
            await interaction.followup.send(embed=emb)

        # 自動修正ボタン（LOW / INFO は除外）
        fixable = [
            f for f in findings
            if f.auto_fixable and f.severity not in (Severity.LOW, Severity.INFO)
        ][:5]

        if fixable:
            view = discord.ui.View(timeout=120)
            for i, f in enumerate(fixable):
                label = f"🔧 {f.title[:20]}"
                if len(f.title) > 20:
                    label += "…"

                button = discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.primary,
                    custom_id=f"fix_{i}_{f.check}"
                )

                async def button_callback(interaction: discord.Interaction, f=f):
                    view = FixView(f, guild, self)
                    await interaction.response.send_message(
                        f"**{f.title}** を修正しますか？\n"
                        "以下のボタンをクリックして確認画面に進んでください。",
                        view=view,
                        ephemeral=True
                    )

                button.callback = button_callback
                view.add_item(button)

            total_fixable = len([f for f in findings if f.auto_fixable and f.severity not in (Severity.LOW, Severity.INFO)])
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