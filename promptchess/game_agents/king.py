from agents import Agent, Runner
from pydantic import BaseModel


class KingState(BaseModel):
    move: str
    reasoning: str


class KingPiece:
    def __init__(self, model):
        self.prompt = (
            'You are a King Piece in a game of Chess. '
            'Your task is to decide on a legal chess move based on current board state and recommendations from other chess factions. '
            'You must ensure your move is legal for a current board state and chess piece. '
        )

        self.agent = Agent(
            name='King Piece', model=model, instructions=self.prompt, output_type=KingState
        )

    async def call(self, debate: str, board_fen: str, board_2d: str, legal_moves: list[str]):
        agent_input = (
            f'\nFaction Statements:\n{debate}'
            f'\n\nCurrent Board State:\nFEN: {board_fen}\n\n{board_2d}'
            f'\n\nAvailable Moves:\n*{"\n*".join(legal_moves)}'
        )
        run_result = await Runner.run(
            self.agent,
            agent_input,
        )
        final_output = run_result.final_output_as(KingState)
        return final_output
