from agents import Agent, Runner
from pydantic import BaseModel


class DebateInput(BaseModel):
    debate_input: str


class ChessFaction:
    def __init__(self, model, piece_name, colour, user_prompt=''):
        self.prompt = (
            f'You are a in control of {colour} {piece_name} Faction in a game of Chess. '
            'Therefore, as their lord, you manage and are responsible for all of them.'
            f'{user_prompt}'
            'You report directly to the King Piece. Provide a useful suggestion in 2-3 sentences. '
        )

        self.agent = Agent(
            name=piece_name,
            model=model,
            instructions=self.prompt,
            output_type=DebateInput,
        )

    async def call(
        self,
        board_state: str,
    ):
        result = await Runner.run(self.agent, f'\nBoard State: {board_state}')
        return result
