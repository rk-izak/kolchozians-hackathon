from agents import Agent, Runner
from pydantic import BaseModel


class EvalState(BaseModel):
    eval: int


class Evaluator:
    def __init__(self, model):
        self.prompt = (
            'You are a evaluator of position in a game of Chess. '
            'Your task is to decide which site is winning and how much. '
            'You have to return single value from -10 to 10 with 0.1 step. '
            'If black is winning than number should be low. '
            'If white is winning than number should be high. '
        )

        self.agent = Agent(
            name='Evaluatore', model=model, instructions=self.prompt, output_type=EvalState
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
