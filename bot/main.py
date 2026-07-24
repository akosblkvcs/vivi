import asyncio
import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot import config, db, delivery, history
from bot.analyze import generate_analysis
from bot.demo.analysis import build_context
from bot.demo.download import DownloadError, download_demo
from bot.demo.sharecode import ShareCodeError
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


@client.tree.command(description="Analyze a CS2 match from its share code")
@app_commands.describe(sharecode="Match share code, e.g. CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx")
async def analyze(interaction: discord.Interaction, sharecode: str) -> None:
    await interaction.response.defer(thinking=True, ephemeral=True)

    # Downloading, parsing and the API call all block; keep the heartbeat alive.
    try:
        demo_path = await asyncio.to_thread(download_demo, sharecode, demos_dir())
    except (ShareCodeError, DownloadError) as exc:
        await interaction.followup.send(f"Couldn't fetch that demo: {exc}", ephemeral=True)
        return

    try:
        ctx = await asyncio.to_thread(build_context, str(demo_path))

        # Store before analyzing, so the match survives an API failure.
        await asyncio.to_thread(history.record_match, ctx)

        text = await asyncio.to_thread(generate_analysis, ctx)
        await delivery.deliver(client, text)
    except Exception:
        logging.exception("analysis failed for %s", sharecode)
        await interaction.followup.send("Something went wrong, check the logs.", ephemeral=True)
        return
    finally:
        # The demo is only needed long enough to parse; never leave it on disk.
        demo_path.unlink(missing_ok=True)

    await interaction.followup.send("Done", ephemeral=True)


def main() -> None:
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
