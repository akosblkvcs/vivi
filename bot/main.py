import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

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


@client.tree.command(description="Health check")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("pong", ephemeral=True)


def main() -> None:
    client.run(TOKEN)


if __name__ == "__main__":
    main()
