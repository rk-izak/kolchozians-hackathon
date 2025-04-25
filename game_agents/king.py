from pydantic import BaseModel
from agents import Agent, Runner
import asyncio

class KingState(BaseModel):
    move_from: str
    move_to: str
    reasoning: str

class KingPiece:
    def __init__(self, model):
        self.prompt = (
            "You are a King Piece in a game of Chess. "
            "Your task is to decide on a legal chess move based on current board state and recommendations from other chess factions. "
            "You must ensure your move is legal for a current board state and chess piece. "
        )

        self.agent = Agent(
            name="King Piece",
            model=model,
            instructions=self.prompt,
            output_type=KingState
        )

    async def call(self, debate: str, board_state: str, legal_moves: list[str]):
        result = await Runner.run(self.agent, f"\nFaction Statements: {debate}\nBoard State: {board_state}\nAvailable Moves: \n*{'\n*'.join(legal_moves)}")
        return result

async def main():
    king = KingPiece(model='gpt-4.1')
    result = await king.call("We should move forward", "Test", ['e1231', 'f1231'])
    # print(result)
    return result.final_output


if __name__ == "__main__":
    print(asyncio.run(main()))

