import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import auditor
from findings import Finding


class FixView(discord.ui.View):
    """自動修正ボタンを表示するView"""
    def __init__(self, finding: Finding, guild: discord.Guild):
        super().__init__(timeout=60)
        self.finding = finding
        self.guild = guild

    @discord.ui.button(label="🔧 安全に修正", style=discord.ButtonStyle.success)
    async def fix_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 権限再確認
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("管理者権限がありません。", ephemeral=True)
            return

        # 修正内容を表示するモーダルを出す
        modal = FixModal(self.finding, self.guild)
        await interaction.response.send_modal(modal)


class FixModal(discord.ui.Modal, title="修正確認"):
    """修正前に確認を取るモーダル"""
    def __init__(self, finding: Finding, guild: discord.Guild):
        super().__init__()
        self.finding = finding
        self.guild = guild

        # 修正内容を表示（説明文）
        self.info = discord.ui.TextInput(
            label="修正内容",
            style=discord.TextStyle.paragraph,
            default=self._build_description(),
            required=False,
        )
        self.add_item(self.info)

        # 確認用チェックボックスはModalでは使えないので、ボタンで対応
        # → 代わりに「実行」ボタンをViewで別途用意

    def _build_description(self) -> str:
        lines = [
            f"以下の修正を実行します：",
            f"",
            f"問題: {self.finding.title}",
            f"対象: {self.finding.target or 'サーバー全体'}",
            f"",
            f"修正内容:",
        ]
        for step in self.finding.fix_steps:
            lines.append(f"  - {step}")
        lines.append("")
        lines.append("この操作は取り消せません。")
        lines.append("本当に実行しますか？")
        return "\n".join(lines)


class ConfirmView(discord.ui.View):
    """実行確認用View（モーダル送信後に表示）"""
    def __init__(self, finding: Finding, guild: discord.Guild):
        super().__init__(timeout=30)
        self.finding = finding
        self.guild = guild

    @discord.ui.button(label="✅ 実行する", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 修正実行
            success = await self._execute_fix()
            
            if success:
                await interaction.followup.send(
                    "✅ 修正が完了しました！\n"
                    "再監査を実行して確認してください。",
                    ephemeral=True
                )
                # 再監査ボタンを表示
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

    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("キャンセルしました。", ephemeral=True)

    async def _execute_fix(self) -> bool:
        """実際の修正処理を呼び出す"""
        check_id = self.finding.check
        guild = self.guild
        
        # 各チェックタイプに応じて修正関数を呼び出す
        if check_id == "everyone_excess":
            # @everyone から権限を削除
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
    """再監査実行ボタン"""
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60)
        self.guild = guild

    @discord.ui.button(label="🔄 再監査する", style=discord.ButtonStyle.primary)
    async def reaudit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ここで /audit を再実行（実際は監査関数を直接呼び出す）
        # 簡易的に /audit コマンドを模倣
        await interaction.response.send_message("再監査を実行中...", ephemeral=True)
        # 実際の実装では run_audit を直接呼び出す


class FixCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="audit-fix", description="特定の問題を自動修正します")
    @app_commands.default_permissions(administrator=True)
    async def audit_fix(self, interaction: discord.Interaction, finding_id: Optional[str] = None):
        """特定のFindingを指定して修正（将来的に実装）"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("管理者権限がありません。", ephemeral=True)
            return

        await interaction.response.send_message(
            "このコマンドは現在開発中です。\n"
            "通常の /audit で表示される「修正」ボタンを使ってください。",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(FixCog(bot))