import logging

import discord

from bot import config


class DeliveryError(RuntimeError):
    """The roast could not be delivered anywhere."""


async def _owner_dm(client: discord.Client) -> discord.abc.Messageable:
    owner = config.owner_id()
    if owner is None:
        raise DeliveryError("DEBUG is on but OWNER_DISCORD_ID is not set.")
    try:
        user = await client.fetch_user(owner)
    except discord.NotFound as exc:
        raise DeliveryError(f"No Discord user with id {owner}.") from exc
    return user


def _public_channel(client: discord.Client) -> discord.abc.Messageable:
    target = config.channel_id()
    if target is None:
        raise DeliveryError("DEBUG is off but CHANNEL_ID is not set.")
    channel = client.get_channel(target)
    if channel is None:
        raise DeliveryError(f"CHANNEL_ID {target} is not visible to the bot.")
    if not isinstance(channel, discord.abc.Messageable):
        raise DeliveryError(f"CHANNEL_ID {target} is not a messageable channel.")
    return channel


async def deliver(client: discord.Client, content: str) -> None:
    """Send a roast to the owner's DMs in debug mode, otherwise to #cs2."""
    if config.debug_mode():
        target = await _owner_dm(client)
        logging.info("DEBUG on — sending roast to owner DM")
    else:
        target = _public_channel(client)
        logging.info("DEBUG off — sending roast to channel %s", config.channel_id())

    await target.send(content)
