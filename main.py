import os
import discord
from discord.ext import commands

# Load token from environment (Render uses environment variables)
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # Needed to read messages

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

bot.run(TOKEN)
