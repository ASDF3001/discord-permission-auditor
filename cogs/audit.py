import discord
from discord import app_commands
from discord.ext import commands
import config
from auditor import check_everyone_visible, check_mention_everyone, run_audit
from findings import build_detail_embeds, build_summary_embed, build_text_report
from risks import calculate_risks

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
        
        # テキストレポートも送信（コピー用）
        text_report = build_text_report(guild.name, findings, risks)
        if len(text_report) <= 2000:
            await interaction.followup.send(f"```\n{text_report}\n```")
        else:
            # 長すぎる場合は分割 or ファイルで送信
            await interaction.followup.send("テキストレポートが長すぎるため、詳細はEmbedをご覧ください。")
        
        # 詳細Embed
        details = build_detail_embeds(findings)
        for emb in details:
            await interaction.followup.send(embed=emb)

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