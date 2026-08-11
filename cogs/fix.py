import discord
from discord import app_commands
from discord.ext import commands
import auditor
from findings import Finding


class FixView(discord.ui.View):
    def __init__(self, finding: Finding, guild: discord.Guild, cog: commands.Cog):
        super().__init__(timeout=120)
        self.finding = finding
        self.guild = guild
        self.cog = cog

    @discord.ui.button(label="🔧 修正する", style=discord.ButtonStyle.success)
    async def fix_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("管理者権限がありません。", ephemeral=True)
            return

        modal = FixConfirmModal(self.finding, self.guild)
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
            success = await self._execute_fix()
            if success:
                await interaction.followup.send(
                    "✅ 修正が完了しました！\n"
                    "再監査を実行して確認してください。",
                    ephemeral=True
                )
                view = ReauditView(self.guild)
                await interaction.followup.send(
                    "🔄 再監査を実行しますか？",
                    view=view,
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 修正に失敗しました。\n"
                    "権限が不足しているか、対象が既に変更されている可能性があります。",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"❌ エラーが発生しました: {str(e)}",
                ephemeral=True
            )

    async def _execute_fix(self) -> bool:
        check_id = self.finding.check
        guild = self.guild

        if check_id == "everyone_excess":
            return await auditor.fix_everyone_permissions(guild, self.finding)
        elif check_id == "server_misconfig":
            if "招待" in self.finding.title:
                return await auditor.fix_invite_permission(guild)
            elif "Webhook" in self.finding.title:
                return await auditor.fix_webhook_permission(guild)
        elif check_id == "role_inheritance":
            return await auditor.fix_redundant_permission(guild, self.finding)
        elif check_id == "everyone_visible":
            return await auditor.fix_channel_visibility(guild, self.finding)
        elif check_id == "mention_everyone":
            return await auditor.fix_mention_permission(guild, self.finding)
        elif check_id == "stale_invites":
            return await auditor.fix_stale_invite(guild, self.finding)
        elif check_id == "integration_webhooks":
            return await auditor.fix_orphaned_webhook(guild, self.finding)
        return False


class ReauditView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60)
        self.guild = guild

    @discord.ui.button(label="🔄 再監査する", style=discord.ButtonStyle.primary)
    async def reaudit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "再監査は `/audit` コマンドを手動で実行してください。\n"
            "（自動再実行は現在開発中です）",
            ephemeral=True
        )


class FixCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="audit-fix", description="特定の問題を自動修正します（開発中）")
    @app_commands.default_permissions(administrator=True)
    async def audit_fix(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("管理者権限がありません。", ephemeral=True)
            return

        await interaction.response.send_message(
            "このコマンドは現在開発中です。\n"
            "通常の `/audit` で表示される「修正」ボタンを使ってください。",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(FixCog(bot))