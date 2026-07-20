"""Discord permission auditor bot.

Slash commands:
  /audit            Run all enabled checks on this server.
  /audit channel    Show channels @everyone can read.
  /audit mention    List non-admin members who can mention @everyone/@here.
  /audit help       Explain the checks and config.
"""

import discord
from discord import app_commands

import config
from auditor import check_everyone_visible, check_mention_everyone, run_audit
from findings import build_detail_embeds, build_summary_embed

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def _guild_only(interaction: discord.Interaction) -> discord.Guild:
    return interaction.guild


@tree.command(name="audit", description="Audit this server's permission gaps.")
async def audit_all(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Run this inside a server.", ephemeral=True)
        return
    await interaction.response.send_message("Scanning... this may take a moment.", ephemeral=True)
    cfg = config.load_config()
    findings, ran = await run_audit(guild, cfg)
    summary = build_summary_embed(guild.name, findings, ran)
    await interaction.followup.send(embed=summary)
    details = build_detail_embeds(findings)
    for emb in details:
        await interaction.followup.send(embed=emb)


@tree.command(name="audit-channel", description="List channels @everyone can read.")
async def audit_channel(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Run this inside a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    cfg = config.load_config()
    findings: list = []
    await check_everyone_visible(guild, cfg, findings)
    if not findings:
        await interaction.followup.send("No readable channels found (or all hidden).")
        return
    for emb in build_detail_embeds(findings):
        await interaction.followup.send(embed=emb)


@tree.command(name="audit-mention", description="List members who can mention @everyone/@here.")
async def audit_mention(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Run this inside a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    cfg = config.load_config()
    findings: list = []
    await check_mention_everyone(guild, cfg, findings)
    if not findings:
        await interaction.followup.send("No non-admin members can mention @everyone/@here.")
        return
    for emb in build_detail_embeds(findings):
        await interaction.followup.send(embed=emb)


@tree.command(name="audit-help", description="Explain the checks and configuration.")
async def audit_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Permission Auditor - Help",
        description="Scans a Discord server for permission gaps and misconfigurations.",
        color=0x566573,
    )
    checks = [
        ("everyone_excess", "@everyone holding dangerous permissions (admin, ban, kick...)."),
        ("external_bot_perms", "External bots holding dangerous permissions."),
        ("server_misconfig", "2FA off, no verification gate, anyone can make invites/webhooks."),
        ("role_inheritance", "Redundant dangerous perms granted by lower roles."),
        ("external_bot_usable", "External bots invokable by any member."),
        ("everyone_visible", "Channels readable by @everyone."),
        ("mention_everyone", "Non-admin members who can ping @everyone/@here."),
        ("stale_invites", "Never-expiring invites."),
        ("owner_admin_roles", "Non-owner members in admin-equivalent roles."),
        ("integration_webhooks", "Webhooks whose creator has left the server."),
    ]
    for cid, desc in checks:
        embed.add_field(name=cid, value=desc, inline=False)
    embed.add_field(
        name="Config",
        value="Set DISCORD_TOKEN and (optionally) GUILD_ID in .env. "
        "Use CONFIG_FILE to toggle checks and whitelist roles/channels/bots. "
        "See README for the JSON format.",
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    if config.GUILD_ID:
        guild = discord.Object(id=config.GUILD_ID)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()
    print(f"Ready as {bot.user} (synced commands)")


def main():
    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
