from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from agents import Agent, Runner
from pydantic import BaseModel, Field

__all__ = [
    "MoveJudgement",
    "JesterState",
    "ChessJester",
]


class MoveJudgement(str, Enum):
    BLUNDER = "blunder"
    MISTAKE = "mistake"
    INACCURACY = "inaccuracy"
    GOOD = "good move"
    BRILLIANT = "brilliant"


class JesterState(BaseModel):
    joke_output: str = Field(..., description="One‑liner about the board situation.")
    judgement: MoveJudgement = Field(..., description="Quality of the last move (heuristic).")


_QUAL_GUIDE = (
    "### How to decide the label (no engine evaluation available)\n"
    "Infer based on *obvious* cues visible in the position: material balance, immediate mating threats, tactical blunders.\n"
    "• If the side that just moved hangs a major piece or allows forced mate → **blunder**.\n"
    "• Losing a minor piece or clear pawn fork without compensation → **mistake**.\n"
    "• Dubious structural/positional concession with no tactic lost → **inaccuracy**.\n"
    "• Neutral, developing, or otherwise solid move → **good move**.\n"
    "• If the move wins material or sets up an unstoppable tactic → **brilliant**.\n"
    "When in doubt, err on the milder label.\n"
)

_SYSTEM_PROMPT_BASE = (
    "You are the Royal Court **Jester** on an enchanted chessboard.\n"
    "Your duties: ① delight the audience with a joke, ② based only on rating the *most recent* move.\n\n"
    "### Personality\n"
    "* Quick‑witted, fond of clever puns.\n"
    "* Sprinkles light medieval flair (‘m'lord’, ‘verily’) but keeps it readable.\n"
    "* Output **two short sentences max**.\n\n"
    + _QUAL_GUIDE +
    "\n### Output format\n"
    "Respond **only** with valid JSON matching the JesterState schema, e.g.:\n"
    "{\"joke_output\": \"A jest!\", \"judgement\": \"mistake\"}\n"
)


class ChessJester:
    """High‑level wrapper exposing `call()` just like a chess piece faction."""

    def __init__(
        self,
        model: str,
        behaviour_file: str | Path | None = None,
        extra_persona: str = "",
    ) -> None:
        self._system_prompt = self._build_prompt(behaviour_file, extra_persona)
        self._agent = Agent(
            name="Chess‑Jester",
            model=model,
            instructions=self._system_prompt,
            output_type=JesterState,
        )

    # ------------------------------------------------------------------
    async def call(self, board_fen: str, board_2d: str) -> JesterState:  # noqa: D401
        """Return joke + judgement based solely on the board snapshot."""

        agent_input = f"FEN: {board_fen}\n\n{board_2d}"
        run_result = await Runner.run(self._agent, agent_input)
        return run_result.final_output_as(JesterState)

    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(behaviour_file: Optional[str | Path], extra_persona: str) -> str:  # noqa: D401
        behaviour_text = ""
        if behaviour_file:
            try:
                behaviour_text = Path(behaviour_file).read_text().strip()
            except FileNotFoundError:
                behaviour_text = "(Could not read behaviour file.)"

        prompt = _SYSTEM_PROMPT_BASE
        if behaviour_text:
            prompt = prompt.replace("### Personality", f"### Personality\n{behaviour_text}\n")
        if extra_persona:
            prompt += f"\n### Extra persona rules\n{extra_persona}\n"
        return prompt
