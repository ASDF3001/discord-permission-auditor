import discord
from discord import app_commands
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="audit-help", description="Explain the checks and configuration.")
    @app_commands.default_permissions(administrator=True)
    async def audit_help(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみ実行できます。", ephemeral=True)
            return

        embed = discord.Embed(
            title="Permission Auditor - ヘルプ",
            description="サーバーの権限設定をスキャンし、セキュリティ上の問題を検出します。",
            color=0x566573,
        )
        checks = [
            ("everyone_excess", "@everyone が危険な権限を持っている"),
            ("server_misconfig", "2FA無効・認証ゲートなし・招待/Webhook作成が自由"),
            ("role_inheritance", "下位ロールが過剰な権限を継承している"),
            ("external_bot_usable", "ユーザーインストールBot/外部アプリを一般メンバーが公開使用できる"),
            ("everyone_visible", "@everyone が読めるチャンネル"),
            ("mention_everyone", "@everyone/@hereをメンションできる一般メンバー"),
            ("stale_invites", "期限切れしない招待リンク"),
            ("owner_admin_roles", "サーバーオーナー以外の管理者相当ロール"),
            ("integration_webhooks", "作成者が退去したWebhook"),
        ]
        for cid, desc in checks:
            embed.add_field(name=cid, value=desc, inline=False)
        embed.add_field(
            name="設定方法",
            value=".env に DISCORD_TOKEN と（オプションで）GUILD_ID を設定。\n"
                  "CONFIG_FILE でチェックのON/OFFやホワイトリストを指定できます。\n"
                  "詳細は README を参照。",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
