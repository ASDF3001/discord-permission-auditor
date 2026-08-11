import discord
from discord.ext import commands
import config
import asyncio

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
    # 同期はここでやる（on_ready が呼ばれた後なら application_id が取れる）
    if config.GUILD_ID:
        guild = discord.Object(id=config.GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
    
    print(f"Ready as {bot.user} (synced commands)")
    
    # デバッグ用：登録されてるコマンドを表示
    cmds = await bot.tree.fetch_commands()
    print("登録済みコマンド:", [c.name for c in cmds])

# setup_hook は on_ready の前に呼ばれるので、ここで cogs を読み込む
async def setup_hook():
    await load_cogs()

bot.setup_hook = setup_hook

def main():
    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    bot.run(config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()