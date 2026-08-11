"""Permission audit logic.

Each check is a standalone coroutine that appends Finding objects to a list.
Heavy lifting uses guild cache (guild.roles, guild.channels, guild.members)
to keep memory and API usage low; only invites fetch live data on demand.
"""

from typing import List

import discord

from findings import Finding, Severity

# Permissions considered dangerous when held by @everyone or external bots.
DANGEROUS_PERMS = {
    "administrator": Severity.CRITICAL,
    "ban_members": Severity.HIGH,
    "kick_members": Severity.HIGH,
    "manage_guild": Severity.HIGH,
    "manage_roles": Severity.HIGH,
    "manage_channels": Severity.HIGH,
    "manage_webhooks": Severity.MEDIUM,
    "manage_emojis": Severity.MEDIUM,
    "manage_nicknames": Severity.MEDIUM,
    "mention_everyone": Severity.MEDIUM,
    "manage_messages": Severity.HIGH,
    "moderate_members": Severity.HIGH,
}


def _perm_label(perm: str) -> str:
    return perm.replace("_", " ").title()


async def check_bot_self(guild: discord.Guild, me: discord.Member, out: List[Finding]) -> None:
    """Verify the bot can actually read what it needs. Not a gap in the server."""
    needed = [
        "view_audit_log",
        "manage_roles",   # to read high-position roles accurately
        "read_messages",
    ]
    missing = [p for p in needed if not getattr(me.guild_permissions, p, False)]
    if missing:
        out.append(
            Finding(
                severity=Severity.INFO,
                check="bot_perm_selfcheck",
                title="Botの権限が不足しています",
                detail="不足している権限: " + ", ".join(_perm_label(p) for p in missing)
                + "。一部の監査結果が不完全になる可能性があります。",
                recommendation="Botに以下の権限を付与してください: " + ", ".join(_perm_label(p) for p in missing),
                description="Bot自身が監査に必要な権限を持っていません。",
                impact="権限が足りないと、正しい監査結果が得られない場合があります。",
                fix_steps=[
                    "サーバー設定 > ロール を開く",
                    "Botのロールを選択",
                    f"「{', '.join(_perm_label(p) for p in missing)}」にチェックを入れる",
                    "保存する"
                ],
                auto_fixable=False,
            )
        )


async def check_everyone_excess(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    everyone = guild.default_role
    for perm, sev in DANGEROUS_PERMS.items():
        if getattr(everyone.permissions, perm, False):
            out.append(
                Finding(
                    severity=sev,
                    check="everyone_excess",
                    title=f"@everyone が危険な権限 '{_perm_label(perm)}' を持っています",
                    detail=f"@everyone に '{_perm_label(perm)}' が付与されています。",
                    target="@everyone",
                    recommendation="この権限を @everyone から削除し、必要なら特定のロールに付与してください。",
                    description=f"@everyone は全メンバーに適用されるロールです。ここに '{_perm_label(perm)}' があると、全員がその権限を持つことになります。",
                    impact=f"悪意のあるメンバーが '{_perm_label(perm)}' を悪用すると、サーバーに深刻な被害が出る可能性があります。",
                    fix_steps=[
                        "サーバー設定 > ロール を開く",
                        "@everyone ロールを選択",
                        f"「{_perm_label(perm)}」のチェックを外す",
                        "保存する"
                    ],
                    auto_fixable=True,
                )
            )


async def check_external_bot_perms(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    for member in guild.members:
        if not member.bot:
            continue
        if cfg.bot_ignored(member):
            continue
        is_external = member.id != guild.owner_id
        for perm, sev in DANGEROUS_PERMS.items():
            if getattr(member.guild_permissions, perm, False):
                out.append(
                    Finding(
                        severity=sev if is_external else Severity.MEDIUM,
                        check="external_bot_perms",
                        title=f"Bot '{member.name}' が危険な権限 '{_perm_label(perm)}' を持っています",
                        detail=f"Bot '{member.name}' に '{_perm_label(perm)}' が付与されています。"
                        + ("" if is_external else " (サーバーオーナー所有)"),
                        target=member.name,
                        recommendation="このBotに本当にその権限が必要か確認し、不要なら削除してください。",
                        description=f"Botに '{_perm_label(perm)}' があると、Botが乗っ取られた場合に悪用されるリスクがあります。",
                        impact=f"悪意のある第三者がBotを操作すると、'{_perm_label(perm)}' を使ってサーバーに被害を与える可能性があります。",
                        fix_steps=[
                            "サーバー設定 > ロール を開く",
                            f"Bot '{member.name}' のロールを選択",
                            f"「{_perm_label(perm)}」のチェックを外す",
                            "保存する"
                        ],
                        auto_fixable=False,  # Botの権限変更はBot自身ではできない場合がある
                    )
                )


async def check_server_misconfig(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    # 2FA requirement not enforced
    if guild.mfa_level == 0:
        out.append(
            Finding(
                severity=Severity.MEDIUM,
                check="server_misconfig",
                title="2FAが有効化されていません",
                detail="サーバーで管理者/モデレーターに2要素認証が要求されていません。",
                recommendation="サーバー設定 > セーフティ設定 から「2FAを要求」を有効にしてください。",
                description="2FAが無効だと、管理者アカウントが乗っ取られた場合にサーバーが危険にさらされます。",
                impact="パスワードが漏洩した場合、アカウントを簡単に乗っ取られ、サーバーを破壊される可能性があります。",
                fix_steps=[
                    "サーバー設定 > セーフティ設定 を開く",
                    "「2FAを要求」をONにする",
                    "保存する"
                ],
                auto_fixable=False,  # サーバー設定変更はBot権限ではできない
            )
        )
    # Open join with no verification level
    if guild.verification_level in (discord.VerificationLevel.none,):
        out.append(
            Finding(
                severity=Severity.LOW,
                check="server_misconfig",
                title="認証レベルが「なし」です",
                detail="新規メンバーがすぐにメッセージを送信できます。",
                recommendation="認証レベルを「低」以上に設定してください。",
                description="認証レベルが低いと、新規参加者がすぐに荒らし行為を行う可能性があります。",
                impact="Raid時に、新規アカウントがすぐに迷惑メッセージを送信できます。",
                fix_steps=[
                    "サーバー設定 > セーフティ設定 を開く",
                    "「認証レベル」を「低」以上に設定",
                    "保存する"
                ],
                auto_fixable=False,
            )
        )
    # Explicit content filter off
    if guild.explicit_content_filter == discord.ContentFilter.disabled:
        out.append(
            Finding(
                severity=Severity.LOW,
                check="server_misconfig",
                title="露骨なコンテンツフィルターが無効です",
                detail="NSFWメディアがスキャンされません。",
                recommendation="フィルターを「全メンバー」に設定してください。",
                description="フィルターが無効だと、不適切な画像がサーバーに投稿される可能性があります。",
                impact="サーバーがDiscordの利用規約に違反するリスクが高まります。",
                fix_steps=[
                    "サーバー設定 > セーフティ設定 を開く",
                    "「露骨なコンテンツフィルター」を「全メンバー」に設定",
                    "保存する"
                ],
                auto_fixable=False,
            )
        )
    # Anyone can create invites (guild-level)
    if guild.default_role.permissions.create_instant_invite:
        out.append(
            Finding(
                severity=Severity.LOW,
                check="server_misconfig",
                title="@everyone が招待を作成できます",
                detail="@everyone に「招待作成」権限があります。",
                target="@everyone",
                recommendation="@everyone から「招待作成」権限を削除してください。",
                description="誰でも招待リンクを作れると、サーバーに無制限に人が入ってくる可能性があります。",
                impact="Raid時に大量の荒らしアカウントが参加する原因になります。",
                fix_steps=[
                    "サーバー設定 > ロール を開く",
                    "@everyone ロールを選択",
                    "「招待作成」のチェックを外す",
                    "保存する"
                ],
                auto_fixable=True,
            )
        )
    # Anyone can manage webhooks (guild-level)
    if guild.default_role.permissions.manage_webhooks:
        out.append(
            Finding(
                severity=Severity.HIGH,
                check="server_misconfig",
                title="@everyone がWebhookを管理できます",
                detail="@everyone に「Webhookの管理」権限があります。",
                target="@everyone",
                recommendation="@everyone から「Webhookの管理」権限を削除してください。",
                description="誰でもWebhookを作成・編集・削除できると、悪用された場合に大量のスパムメッセージを送信できます。",
                impact="攻撃者がWebhookを悪用して、サーバーに偽装メッセージを送信できます。",
                fix_steps=[
                    "サーバー設定 > ロール を開く",
                    "@everyone ロールを選択",
                    "「Webhookの管理」のチェックを外す",
                    "保存する"
                ],
                auto_fixable=True,
            )
        )


async def check_role_inheritance(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    sorted_roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
    for role in sorted_roles:
        if cfg.role_ignored(role):
            continue
        if role.is_default():
            continue
        for perm, sev in DANGEROUS_PERMS.items():
            if getattr(role.permissions, perm, False):
                higher_redundant = any(
                    (r.position > role.position and getattr(r.permissions, perm, False))
                    for r in sorted_roles
                )
                if higher_redundant:
                    out.append(
                        Finding(
                            severity=Severity.LOW,
                            check="role_inheritance",
                            title=f"冗長な権限 '{_perm_label(perm)}' がロール '{role.name}' にあります",
                            detail=f"ロール '{role.name}' は '{_perm_label(perm)}' を持っていますが、上位ロールも同じ権限を持っています。",
                            target=role.name,
                            recommendation="下位ロールからこの権限を削除して、権限の範囲を狭めてください。",
                            description="同じ権限が複数のロールに付与されていると、権限の管理が複雑になり、誤って権限を付与しやすくなります。",
                            impact="権限の継承が複雑だと、意図しないメンバーに権限が渡る可能性があります。",
                            fix_steps=[
                                "サーバー設定 > ロール を開く",
                                f"ロール '{role.name}' を選択",
                                f"「{_perm_label(perm)}」のチェックを外す",
                                "保存する"
                            ],
                            auto_fixable=True,
                        )
                    )


async def check_external_bot_usable(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    if not guild.default_role.permissions.use_application_commands:
        return
    for member in guild.members:
        if not member.bot or member.id == guild.owner_id:
            continue
        if cfg.bot_ignored(member):
            continue
        confined = any(
            ch.permissions_for(member).use_application_commands is False
            for ch in guild.channels
        )
        if not confined:
            out.append(
                Finding(
                    severity=Severity.LOW,
                    check="external_bot_usable",
                    title=f"Bot '{member.name}' が全メンバーに使えます",
                    detail=f"Bot '{member.name}' は誰でもスラッシュコマンドを実行できます。",
                    target=member.name,
                    recommendation="Botを特定のロール/チャンネルに制限してください。",
                    description="誰でもBotを使えると、悪意のあるユーザーがBotを悪用する可能性があります。",
                    impact="Botが危険な権限を持っている場合、誰でもその権限を間接的に使えることになります。",
                    fix_steps=[
                        "サーバー設定 > チャンネル を開く",
                        "Botを制限したいチャンネルを選択",
                        "「詳細な権限」からBotの「スラッシュコマンドを使用」をOFFにする",
                        "または、Botのロールから「スラッシュコマンドを使用」を削除する"
                    ],
                    auto_fixable=False,  # チャンネル権限の変更は複雑なので自動化しない
                )
            )


async def check_everyone_visible(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    visible = []
    for channel in guild.channels:
        if cfg.channel_ignored(channel):
            continue
        if isinstance(channel, (discord.CategoryChannel,)):
            continue
        perms = channel.permissions_for(guild.default_role)
        if perms.read_messages or perms.view_channel:
            name = getattr(channel, "name", str(channel))
            visible.append(f"#{name}")
    if visible:
        out.append(
            Finding(
                severity=Severity.INFO,
                check="everyone_visible",
                title=f"@everyone が {len(visible)} 個のチャンネルを読めます",
                detail="読めるチャンネル: " + ", ".join(visible[:40]) + (" ..." if len(visible) > 40 else ""),
                target="@everyone",
                recommendation="機密チャンネルは @everyone からアクセスを制限してください。",
                description="@everyone がチャンネルを読める場合、サーバーに参加している全員がその内容を見られます。",
                impact="内部向けの情報が外部のユーザーに見える可能性があります。",
                fix_steps=[
                    "チャンネルを右クリック > チャンネルを編集",
                    "「権限」タブを開く",
                    "@everyone の「チャンネルを見る」をOFFにする",
                    "保存する"
                ],
                auto_fixable=True,
            )
        )


async def check_mention_everyone(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    allowed = []
    for member in guild.members:
        if member.bot:
            continue
        if member.guild_permissions.administrator:
            continue
        if member.guild_permissions.mention_everyone:
            name = getattr(member, "display_name", member.name)
            allowed.append(name)
    if allowed:
        out.append(
            Finding(
                severity=Severity.HIGH,
                check="mention_everyone",
                title=f"{len(allowed)} 人の一般メンバーが @everyone/@here をメンションできます",
                detail="メンション可能なメンバー: " + ", ".join(allowed[:40]) + (" ..." if len(allowed) > 40 else ""),
                recommendation="一般メンバーから「@everyone/@hereをメンション」権限を削除してください。",
                description="@everyone/@hereメンションはサーバー全体に通知を送る機能です。",
                impact="悪用されると全メンバーに迷惑通知が届き、Raid時に混乱を招きます。",
                fix_steps=[
                    "サーバー設定 > ロール を開く",
                    "該当メンバーが持つロールを選択",
                    "「@everyone/@hereをメンション」のチェックを外す",
                    "保存する"
                ],
                auto_fixable=True,
            )
        )


async def check_stale_invites(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    if not guild.me or not guild.me.guild_permissions.manage_guild:
        return
    try:
        invites = await guild.invites()
    except discord.Forbidden:
        return
    for inv in invites:
        if inv.max_age == 0:
            out.append(
                Finding(
                    severity=Severity.LOW,
                    check="stale_invites",
                    title=f"期限切れしない招待リンクがあります (コード: {inv.code})",
                    detail=f"招待コード {inv.code} は無期限です"
                    + (f" (作成者: {inv.inviter})" if inv.inviter else "")
                    + f", 使用回数: {inv.uses}回",
                    target=inv.code,
                    recommendation="期限を設定するか、不要なら削除してください。",
                    description="無期限の招待リンクは、サーバーにいつでも誰でも参加できる状態を作ります。",
                    impact="Raid時に大量の荒らしがこのリンクを使って参加する可能性があります。",
                    fix_steps=[
                        "サーバー設定 > 招待 を開く",
                        "該当の招待リンクを探す",
                        "削除するか、有効期限を設定する"
                    ],
                    auto_fixable=True,
                )
            )


async def check_owner_admin_roles(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    for role in guild.roles:
        if cfg.role_ignored(role):
            continue
        if not role.permissions.administrator:
            continue
        for member in role.members:
            if member.id == guild.owner_id or member.bot:
                continue
            out.append(
                Finding(
                    severity=Severity.HIGH,
                    check="owner_admin_roles",
                    title=f"サーバーオーナー以外に管理者ロール '{role.name}' が付与されています",
                    detail=f"メンバー '{member.display_name}' が管理者ロール '{role.name}' を持っています。",
                    target=member.name,
                    recommendation="本当に必要なメンバーだけに管理者権限を付与してください。",
                    description="管理者権限はサーバーを完全に制御できるため、信頼できる少数のメンバーだけに付与すべきです。",
                    impact="このメンバーのアカウントが乗っ取られると、サーバー全体が破壊される可能性があります。",
                    fix_steps=[
                        "サーバー設定 > ロール を開く",
                        f"ロール '{role.name}' を選択",
                        "該当メンバーをロールから削除する",
                        "または、ロールから管理者権限を削除する"
                    ],
                    auto_fixable=False,  # メンバーからロールを剥奪するのは危険
                )
            )


async def check_integration_webhooks(guild: discord.Guild, cfg, out: List[Finding]) -> None:
    if not guild.me or not guild.me.guild_permissions.manage_webhooks:
        return
    try:
        hooks = await guild.webhooks()
    except discord.Forbidden:
        return
    bot_ids = {m.id for m in guild.members if m.bot}
    for hook in hooks:
        creator_gone = hook.user is None or (hook.user.id not in bot_ids and hook.user.id not in {m.id for m in guild.members})
        if creator_gone:
            out.append(
                Finding(
                    severity=Severity.MEDIUM,
                    check="integration_webhooks",
                    title=f"作成者が退去したWebhookがあります (チャンネル: #{hook.channel.name})",
                    detail=f"Webhook '{hook.name}' の作成者がサーバーにいません。",
                    target=hook.name or "unknown",
                    recommendation="不要なWebhookは削除してください。",
                    description="作成者がいないWebhookは管理されず、悪用されるリスクがあります。",
                    impact="攻撃者がこのWebhookを見つけて、偽装メッセージを送信する可能性があります。",
                    fix_steps=[
                        "サーバー設定 > Webhooks を開く",
                        "該当のWebhookを探す",
                        "削除する"
                    ],
                    auto_fixable=True,
                )
            )


# Ordered registry used by the runner.
ALL_CHECKS = [
    ("bot_perm_selfcheck", check_bot_self),
    ("everyone_excess", check_everyone_excess),
    ("external_bot_perms", check_external_bot_perms),
    ("server_misconfig", check_server_misconfig),
    ("role_inheritance", check_role_inheritance),
    ("external_bot_usable", check_external_bot_usable),
    ("everyone_visible", check_everyone_visible),
    ("mention_everyone", check_mention_everyone),
    ("stale_invites", check_stale_invites),
    ("owner_admin_roles", check_owner_admin_roles),
    ("integration_webhooks", check_integration_webhooks),
]


async def run_audit(guild: discord.Guild, cfg) -> tuple[List[Finding], int]:
    """Run all enabled checks. Returns (findings, number_of_checks_run)."""
    out: List[Finding] = []
    me = guild.me
    ran = 0
    for check_id, fn in ALL_CHECKS:
        if not cfg.is_enabled(check_id):
            continue
        ran += 1
        try:
            if check_id == "bot_perm_selfcheck":
                await fn(guild, me, out)
            else:
                await fn(guild, cfg, out)
        except discord.Forbidden:
            out.append(
                Finding(
                    severity=Severity.INFO,
                    check=check_id,
                    title="チェックをスキップしました",
                    detail=f"Botに '{check_id}' を実行するための権限がありません。",
                    recommendation="Botに必要な権限を付与してください。",
                    description="権限不足のためこのチェックは実行できませんでした。",
                    impact="監査結果が不完全になる可能性があります。",
                    fix_steps=[
                        "サーバー設定 > ロール を開く",
                        "Botのロールを選択",
                        "必要な権限を付与する",
                        "保存する"
                    ],
                    auto_fixable=False,
                )
            )
        except Exception:
            continue
    return out, ran