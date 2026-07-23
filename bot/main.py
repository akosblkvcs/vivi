import asyncio
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot import config, delivery, history
from bot.demo.analysis import build_context
from bot.demo.workspace import demos_dir, purge_orphans
from bot.roast import generate_roast

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["DISCORD_TOKEN"]
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
        logging.info("Connected as %s (%s)", user, user.id)
    logging.info("DEBUG=%s", config.debug_mode())
    purge_orphans()
    history.init_schema()


@client.tree.command(description="Health check")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("pong", ephemeral=True)


@client.tree.command(description="Parse a demo already on the server and roast the players")
@app_commands.describe(filename="A .dem file sitting in the server's data/demos directory")
async def roast(interaction: discord.Interaction, filename: str) -> None:
    # Only the final component: a filename is user input and must not escape data/demos.
    demo_path = demos_dir() / Path(filename).name
    if not demo_path.is_file():
        await interaction.response.send_message(
            f"Nincs ilyen demo: `{demo_path.name}`", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        # Parsing and the API call both block; keep the gateway heartbeat alive.
        ctx = await asyncio.to_thread(build_context, str(demo_path))
        # Store before roasting, so the match survives an API failure. Baselines
        # exclude it by demo_key, so it cannot contaminate its own comparison.
        await asyncio.to_thread(history.record_match, ctx)
        text = await asyncio.to_thread(generate_roast, ctx)
        await delivery.deliver(client, text)
    except Exception:
        logging.exception("roast failed for %s", demo_path.name)
        await interaction.followup.send("Elszállt a feldolgozás, nézd a logot.", ephemeral=True)
        return

    where = "DM-ben" if config.debug_mode() else "a csatornába"
    await interaction.followup.send(f"Kész, elküldtem {where}.", ephemeral=True)


def main() -> None:
    client.run(TOKEN)


if __name__ == "__main__":
    main()
