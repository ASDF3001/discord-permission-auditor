import discord
from discord import app_commands
from discord.ext import commands
import config
from auditor import run_audit
from findings import Finding, Severity
from risks import calculate_risks


class FixSelect(discord.ui.Select):
    def __init__(self, findings: list, guild: discord.Guild):
        self.findings = findings
        self.guild = guild

        options = []
        for i, f in enumerate(findings[:10]):
            label = f"{f.severity.name}: {f.title[:30]}"
            if len(label) > 50:
                label = label[:47] + "..."
            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(i),
                    description=f"対象: {f.target or 'サーバー全体'}"
                )
            )

        super().__init__(
            placeholder="修正する問題を選択してください",
            options=options,
            max_values=1,
            min_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        finding = self.findings[selected_index]
        print(f"🔧 修正選択: {finding.severity.name} - {finding.title}")
        modal = FixConfirmModal(finding, self.guild)
        await interaction.response.send_modal(modal)


class FixConfirmModal(discord.ui.Modal, title="修正確認"):
    def __init__(self, finding: Finding, guild: discord.Guild):
        super().__init__()
        self.finding = finding
        self.guild = guild

        self.info = discord.ui.TextInput(
            label="以下の修正を実行します",
            style=discord.TextStyle.paragraph,
            default=self._build_description(),
            required=False,
        )
        self.add_item(self.info)

    def _build_description(self) -> str:
        lines = [
            f"問題: {self.finding.title}",
            f"対象: {self.finding.target or 'サーバー全体'}",
            "",
            "修正手順:",
        ]
        for step in self.finding.fix_steps[:5]:
            lines.append(f"  • {step}")
        lines.append("")
        lines.append("この操作は取り消せません。本当に実行しますか？")
        return "\n".join(lines)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            print(f"🔧 修正実行開始: {self.finding.check}")
            success = await self._execute_fix()
            if success:
                print(f"✅ 修正成功: {self.finding.check}")
                await interaction.followup.send(
                    "✅ 修正が完了しました！",
                    ephemeral=True
                )
                view = ReauditView(self.guild)
                await interaction.followup.send(
                    "🔄 再監査を実行しますか？",
                    view=view,
                    ephemeral=True
                )
            else:
                print(f"❌ 修正失敗: {self.finding.check}")
                await interaction.followup.send(
                    "❌ 修正に失敗しました。\n"
                    "権限が不足しているか、対象が既に変更されている可能性があります。",
                    ephemeral=True
                )
        except Exception as e:
            print(f"❌ 修正エラー: {e}")
            await interaction.followup.send(
                f"❌ エラーが発生しました: {str(e)}",
                ephemeral=True
            )

    async def _execute_fix(self) -> bool:
        from auditor import (
            fix_everyone_permissions,
            fix_invite_permission,
            fix_webhook_permission,
            fix_redundant_permission,
            fix_channel_visibility,
            fix_mention_permission,
            fix_stale_invite,
            fix_orphaned_webhook,
            fix_external_bot_usable,
        )

        check_id = self.finding.check
        guild = self.guild

        # 権限チェック（Bot自身の権限）
        me = guild.me
        external_bot_channel_target = (
            check_id == "external_bot_usable"
            and self.finding.target
            and self.finding.target.startswith("#")
        )
        needs_roles = check_id in {"everyone_excess", "role_inheritance"} or (
            check_id == "external_bot_usable" and not external_bot_channel_target
        )
        needs_channels = check_id == "everyone_visible" or (
            check_id == "external_bot_usable" and external_bot_channel_target
        )
        if needs_roles and not me.guild_permissions.manage_roles:
            print("❌ Botに manage_roles 権限がありません")
            return False
        if needs_channels and not me.guild_permissions.manage_channels:
            print("❌ Botに manage_channels 権限がありません")
            return False

        if check_id == "everyone_excess":
            return await fix_everyone_permissions(guild, self.finding)
        elif check_id == "server_misconfig":
            if "招待" in self.finding.title:
                return await fix_invite_permission(guild)
            elif "Webhook" in self.finding.title:
                return await fix_webhook_permission(guild)
        elif check_id == "role_inheritance":
            return await fix_redundant_permission(guild, self.finding)
        elif check_id == "everyone_visible":
            return await fix_channel_visibility(guild, self.finding)
        elif check_id == "mention_everyone":
            return await fix_mention_permission(guild, self.finding)
        elif check_id == "external_bot_usable":
            return await fix_external_bot_usable(guild, self.finding)
        elif check_id == "stale_invites":
            return await fix_stale_invite(guild, self.finding)
        elif check_id == "integration_webhooks":
            return await fix_orphaned_webhook(guild, self.finding)
        print(f"❌ 未対応のチェック: {check_id}")
        return False


class ReauditView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60)
        self.guild = guild

    @discord.ui.button(label="🔄 再監査する", style=discord.ButtonStyle.primary)
    async def reaudit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        print("🔄 再監査実行")

        cfg = config.load_config()
        findings, ran = await run_audit(self.guild, cfg)
        risks = calculate_risks(findings)

        print(f"🔍 再監査結果: {len(findings)}件")

        from findings import build_summary_embed
        summary = build_summary_embed(self.guild.name, findings, ran, risks=risks)
        await interaction.followup.send(embed=summary)

        fixable_count = len([
            f for f in findings
            if f.auto_fixable and f.severity not in (Severity.LOW, Severity.INFO)
        ])
        if fixable_count > 0:
            await interaction.followup.send(
                f"🔧 **{fixable_count}件**の問題が自動修正可能です。\n"
                "修正する場合は `/fix` コマンドを実行してください。",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "✅ 自動修正可能な問題はありません。",
                ephemeral=True
            )


class FixCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fix", description="自動修正可能な問題を表示して修正します")
    @app_commands.default_permissions(administrator=True)
    async def fix(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("管理者権限がありません。", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        await interaction.response.send_message("監査を実行中…少々お待ちください。", ephemeral=True)

        cfg = config.load_config()
        findings, _ = await run_audit(guild, cfg)

        print(f"🔍 /fix: 全Finding {len(findings)}件")

        fixable = [
            f for f in findings
            if f.auto_fixable and f.severity not in (Severity.LOW, Severity.INFO)
        ]

        print(f"🔧 修正可能: {len(fixable)}件")
        for f in fixable:
            print(f"  - {f.severity.name}: {f.title}")

        if not fixable:
            await interaction.followup.send(
                "✅ 自動修正可能な問題はありません。",
                ephemeral=True
            )
            return

        view = discord.ui.View()
        select = FixSelect(fixable, guild)
        view.add_item(select)

        await interaction.followup.send(
            f"🔧 **{len(fixable)}件**の問題が自動修正可能です。\n"
            "修正する問題を選択してください。",
            view=view,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(FixCog(bot))
