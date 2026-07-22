import logging
import os
from pathlib import Path

import anthropic
from anthropic import beta_tool
from anthropic.types.beta import BetaOutputConfigParam, BetaThinkingConfigParam

from bot import tools
from bot.demo.analysis import MatchContext

# Sonnet 5 is the cost/quality sweet spot: near-Opus writing on a short creative
# task at a fraction of the price. Raise the effort level (or move to
# claude-opus-4-8) if the recaps come out flat.
MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000

# Each tool call is a round trip. Enough to investigate properly, bounded so a
# confused model cannot spend money in a loop.
MAX_ITERATIONS = 12

THINKING: BetaThinkingConfigParam = {"type": "adaptive"}
OUTPUT_CONFIG: BetaOutputConfigParam = {"effort": "low"}

TARGET_CHARS = 1500
DISCORD_LIMIT = 2000

PROMPTS = Path(__file__).parent / "prompts"
PROMPT_FILES = ("roast_hu.txt", "watchlist_hu.txt", "praise_hu.txt")

KICKOFF = (
    "Investigate this CS2 match with the tools available, then write the "
    "Hungarian recap. Do not describe your investigation — reply with the "
    "finished recap only."
)


def load_system_prompt(persona: str = "") -> str:
    parts = [(PROMPTS / name).read_text(encoding="utf-8").strip() for name in PROMPT_FILES]
    system = "\n\n".join(parts).format(target=TARGET_CHARS)
    if persona:
        system += f"\n\nExtra context about this group:\n{persona}\n"
    return system


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set — the roast step cannot run without it.")
    return anthropic.Anthropic()


def _roster_notes(ctx: MatchContext) -> str:
    notes = ctx.roster.notes
    if not notes:
        return ""
    lines = "\n".join(f"- {name}: {note}" for name, note in notes)
    return f"\n\nNotes on specific people:\n{lines}\n"


def generate_roast(ctx: MatchContext, *, persona: str = "") -> str:
    """Let Claude investigate the match, then return the Hungarian recap."""
    system = load_system_prompt(persona) + _roster_notes(ctx)

    tools.set_context(ctx)
    try:
        runner = _client().beta.messages.tool_runner(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            max_iterations=MAX_ITERATIONS,
            system=system,
            tools=[beta_tool(fn) for fn in tools.ALL_TOOLS],
            thinking=THINKING,
            output_config=OUTPUT_CONFIG,
            messages=[{"role": "user", "content": KICKOFF}],
        )
        response = runner.until_done()
    finally:
        tools.set_context(None)

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this recap.")

    usage = response.usage
    logging.info("roast tokens: in=%s out=%s", usage.input_tokens, usage.output_tokens)

    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise RuntimeError(f"Claude returned no text (stop_reason={response.stop_reason}).")

    if len(text) > DISCORD_LIMIT:
        logging.warning("roast was %d chars, trimming to %d", len(text), DISCORD_LIMIT)
        text = text[: DISCORD_LIMIT - 1].rstrip() + "…"
    return text
