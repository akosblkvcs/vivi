import logging
import re

import discord

from bot import config

_SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)


class DeliveryError(RuntimeError):
    """The analysis could not be delivered anywhere."""


def _messages(content: str) -> list[str]:
    """Split the recap into the messages to send, on its own separators."""
    return [section.strip() for section in _SEPARATOR.split(content) if section.strip()]


async def _dev_dm(client: discord.Client) -> discord.abc.Messageable:
    dev = config.dev_id()

    if dev is None:
        raise DeliveryError("DEBUG is on but DEV_DISCORD_ID is not set")

    try:
        user = await client.fetch_user(dev)
    except discord.NotFound as exc:
        raise DeliveryError(f"no Discord user with id {dev}") from exc

    return user


def _public_channel(client: discord.Client) -> discord.abc.Messageable:
    target = config.channel_id()

    if target is None:
        raise DeliveryError("DEBUG is off but CHANNEL_ID is not set")

    channel = client.get_channel(target)
    if channel is None:
        raise DeliveryError(f"CHANNEL_ID {target} is not visible to the bot")
    if not isinstance(channel, discord.abc.Messageable):
        raise DeliveryError(f"CHANNEL_ID {target} is not a messageable channel")

    return channel


async def deliver(client: discord.Client, content: str) -> None:
    """Send the analysis to the developer in debug mode, otherwise to the public channel."""
    messages = _messages(content)

    if config.debug_mode():
        target = await _dev_dm(client)
        logging.info("sending %d message(s) to developer", len(messages))
    else:
        target = _public_channel(client)
        logging.info("sending %d message(s) to channel %s", len(messages), config.channel_id())

    for message in messages:
        await target.send(message)
