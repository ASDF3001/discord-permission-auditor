import discord
from discord.ext import commands
import config

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def load_cogs():
    await bot.load_extension("cogs.audit")
    await bot.load_extension("cogs.help")
    await bot.load_extension("cogs.fix")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # 登録されてるコマンドを確認（デバッグ用）
    cmds = await bot.tree.fetch_commands()
    print(f"現在の登録コマンド: {[c.name for c in cmds]}")

async def main():
    async with bot:
        # cogsを読み込んでから同期
        await load_cogs()
        
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
        
        print("コマンド同期完了")
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set.")
    import asyncio
    asyncio.run(main())