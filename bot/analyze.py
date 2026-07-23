import logging
import os

import anthropic
from anthropic import beta_tool
from anthropic.types.beta import BetaOutputConfigParam, BetaThinkingConfigParam

from bot import tools
from bot.config import DATA_DIR
from bot.demo.analysis import MatchContext

MODEL = "claude-opus-4-8"
MAX_TOKENS = 8000

MAX_ITERATIONS = 12

THINKING: BetaThinkingConfigParam = {"type": "adaptive"}
OUTPUT_CONFIG: BetaOutputConfigParam = {"effort": "low"}

PROMPT_FILE = DATA_DIR / "prompt.md"


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    return anthropic.Anthropic()


def _roster_intro(ctx: MatchContext) -> str:
    """Name the roster players who actually appear in this match."""
    me: list[str] = []
    friends: list[str] = []
    for p in ctx.stats.players.values():
        role = ctx.roster.role_of(p.steamid)
        if role == "self":
            me.append(ctx.display(p.steamid, p.name))
        elif role == "friend":
            friends.append(ctx.display(p.steamid, p.name))

    lines = ["This match:"]
    lines.append(f"- I am: {', '.join(me)}" if me else "- I did not play this match.")
    lines.append(
        f"- The friends who played: {', '.join(friends)}"
        if friends
        else "- None of the friends played this match."
    )
    lines.append("- Everyone else is a random teammate or enemy.")
    return "\n".join(lines)


def generate_analysis(ctx: MatchContext) -> str:
    """Let Claude investigate the match with the tools, then return the recap."""
    prompt = PROMPT_FILE.read_text(encoding="utf-8").strip() + "\n\n" + _roster_intro(ctx)

    tools.set_context(ctx)
    try:
        runner = _client().beta.messages.tool_runner(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            max_iterations=MAX_ITERATIONS,
            tools=[beta_tool(fn) for fn in tools.ALL_TOOLS],
            thinking=THINKING,
            output_config=OUTPUT_CONFIG,
            messages=[{"role": "user", "content": prompt}],
        )
        response = runner.until_done()
    finally:
        tools.set_context(None)

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this recap")

    usage = response.usage
    logging.info("analysis tokens: in=%s out=%s", usage.input_tokens, usage.output_tokens)

    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise RuntimeError(f"Claude returned no text (stop_reason={response.stop_reason})")

    return text
