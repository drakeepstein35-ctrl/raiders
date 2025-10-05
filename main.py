import discord
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime

# =====================
# CONFIGURATION
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")    # Replace with your bot token
OWNER_ID = 123456789012345678     # Replace with your Discord user ID
CUTOFF_ROLE_ID = 987654321098765432  # Replace with the cutoff role ID
PREFIX = "!"                      # Bot command prefix

# =====================
# BOT SETUP
# =====================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- small web app to bind port
async def handle(req):
    return web.Response(text="ok")

async def start_webserver():
    port = int(os.environ.get("PORT", "10000"))
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Webserver listening on 0.0.0.0:{port}")

# --- Speed Profiles (ms delays)
SPEED_MODES = {
    "safe": {"kick": 1200, "channel": 1200, "role": 1200},   # safest, ~50 kicks/min
    "fast": {"kick": 900, "channel": 900, "role": 900},      # balanced, ~65 kicks/min
    "aggressive": {"kick": 600, "channel": 700, "role": 700} # riskier, may hit limits
}

async def wait(ms: int):
    """Helper to wait in milliseconds."""
    await asyncio.sleep(ms / 1000)

# =====================
# EVENTS
# =====================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

# =====================
# COMMANDS
# =====================
@bot.command()
@commands.guild_only()
async def clean_server(ctx, mode: str = "safe"):
    """Clean inactive members, roles, and channels.
    Usage: !clean_server [safe|fast|aggressive]
    """
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Only the configured server owner can run this command.")

    if mode not in SPEED_MODES:
        return await ctx.send("⚠️ Invalid mode. Choose from: safe, fast, aggressive")

    delays = SPEED_MODES[mode]
    await ctx.send(f"⚙️ Starting cleanup in **{mode.upper()}** mode...")

    guild = ctx.guild
    role = guild.get_role(CUTOFF_ROLE_ID)
    if not role:
        return await ctx.send("❌ Cutoff role not found. Check the ID or permissions.")

    me = guild.me
    if me.top_role.position <= role.position:
        return await ctx.send("⚠️ Bot role must be above the cutoff role in hierarchy.")

    # --- Backup (roles + channels) ---
    backup_data = {
        "guild": {"id": guild.id, "name": guild.name},
        "timestamp": datetime.utcnow().isoformat(),
        "roles": [
            {"id": r.id, "name": r.name, "position": r.position,
             "permissions": r.permissions.value, "managed": r.managed}
            for r in guild.roles
        ],
        "channels": [
            {"id": ch.id, "name": ch.name, "type": str(ch.type), "position": ch.position}
            for ch in guild.channels
        ]
    }
    os.makedirs("backups", exist_ok=True)
    backup_path = f"backups/{guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2)
    await ctx.send(f"💾 Backup saved at `{backup_path}`")

    # --- Kick members below cutoff ---
    kicked = 0
    async for member in guild.fetch_members(limit=None):
        if member.bot or member.id == guild.owner_id:
            continue
        if member.top_role.position < role.position:
            try:
                await member.kick(reason="Server clean (inactive member)")
                kicked += 1
                await wait(delays["kick"])
            except Exception as e:
                print(f"Failed to kick {member}: {e}")
    await ctx.send(f"✅ Kicked {kicked} inactive members.")

    # --- Delete channels ---
    deleted_channels = 0
    for ch in list(guild.channels):
        try:
            await ch.delete(reason="Server clean")
            deleted_channels += 1
            await wait(delays["channel"])
        except Exception as e:
            print(f"Failed to delete channel {ch}: {e}")
    await ctx.send(f"🗑️ Deleted {deleted_channels} channels.")

    # --- Delete roles ---
    deleted_roles = 0
    for r in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if r.managed or r.id == guild.id:
            continue
        if r.position < role.position and me.top_role.position > r.position:
            try:
                await r.delete(reason="Server clean")
                deleted_roles += 1
                await wait(delays["role"])
            except Exception as e:
                print(f"Failed to delete role {r}: {e}")
    await ctx.send(f"🧹 Deleted {deleted_roles} roles.")

    await ctx.send("✅ **Server clean complete.**")

async def main():
    # start webserver and bot together
    await start_webserver()
    await bot.start(os.environ["DISCORD_TOKEN"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
