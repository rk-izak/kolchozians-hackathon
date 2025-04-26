from pydantic import BaseModel
from agents import Agent, Runner
import asyncio


class SummaryState(BaseModel):
    summary: str
    inputs: list[str]


class SummaryAgent:
    def __init__(self, model):
        self.prompt = (
            'You are a summary writer assistant. '
            'Write a summary representing given Chess Piece group based on their inputs. '
        )

        self.agent = Agent(
            name='Summarizer', model=model, instructions=self.prompt, output_type=SummaryState
        )

    async def call(self, chess_inputs, piece_name):
        result = await Runner.run(
            self.agent,
            f'\nGroup Represented: {piece_name}\nPiece Inputs: \n*{"\n*".join(chess_inputs)}',
        )
        return result
