import asyncio
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot import config, db, delivery, history
from bot.analyze import generate_analysis
from bot.demo.analysis import build_context
from bot.demo.workspace import demos_dir, purge_orphans

load_dotenv()
logging.basicConfig(level=logging.INFO)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])


class Vivi(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)


client = Vivi()


@client.event
async def on_ready() -> None:
    if (user := client.user) is not None:
        logging.info("connected as %s (%s)", user, user.id)
    logging.info("DEBUG=%s", config.debug_mode())
    purge_orphans()
    db.init_schema()


@client.tree.command(description="Health check")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("pong", ephemeral=True)


@client.tree.command(description="Analyze a CS2 match")
@app_commands.describe(filename="Name of the .dem file")
async def analyze(interaction: discord.Interaction, filename: str) -> None:
    demo_path = demos_dir() / Path(filename).name
    if not demo_path.is_file():
        await interaction.response.send_message(f"No such demo: `{demo_path.name}`", ephemeral=True)
        return

    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        # Parsing and the API call both block; keep the gateway heartbeat alive.
        ctx = await asyncio.to_thread(build_context, str(demo_path))

        # Store before analyzing, so the match survives an API failure.
        await asyncio.to_thread(history.record_match, ctx)

        # Generate the analysis.
        text = await asyncio.to_thread(generate_analysis, ctx)

        # Deliver the analysis to the appropriate channel.
        await delivery.deliver(client, text)
    except Exception:
        logging.exception("analysis failed for %s", demo_path.name)
        await interaction.followup.send("Something went wrong, check the logs.", ephemeral=True)
        return

    await interaction.followup.send("Done", ephemeral=True)


def main() -> None:
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
