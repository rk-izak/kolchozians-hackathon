from agents import Agent, Runner
from pydantic import BaseModel


class EvalState(BaseModel):
    eval: int


class Evaluator:
    def __init__(self, model):
        self.prompt = (
            "You are an **expert chess engine** evaluating the current board position.\n\n"
            "### Task\n"
            "Return **one** decimal value in the range **-10.0 to 10.0**, using 0.1 increments, that indicates how favorable the position is **for White**.\n"
            "• Positive numbers (> 0)  → White is better.\n"
            "• Negative numbers (< 0) → Black is better.\n"
            "• +10.0  → forced win for White.\n"
            "• -10.0 → forced win for Black.\n"
            "•  0.0   → perfectly equal.\n\n"
            "Do **not** output any other words, symbols, or explanation.\n\n"
            "Think through the position step-by-step **internally**, but reveal **only** the final number."
        )
        self.agent = Agent(
            name='Evaluator', model=model, instructions=self.prompt, output_type=EvalState
        )

    async def call(self, board_fen: str, board_2d: str):
        agent_input = (
            f'\n\nCurrent Board State:\nFEN: {board_fen}\n\n{board_2d}'
        )
        run_result = await Runner.run(
            self.agent,
            agent_input,
        )
        final_output = run_result.final_output_as(EvalState)
        return final_output
