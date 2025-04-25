from pydantic import BaseModel
from agents import Agent, Runner
import asyncio

class KingState(BaseModel):
    decision: str
    reasoning: str

class KingPiece:
    def __init__(self,):
        self.prompt = (
            "You are a King Piece in a game of Chess. "
            "Your task is to decide on a legal chess move based on current board state and recommendations from other chess pieces. "
            "You must ensure your move is legal for a current board state and chess piece. "
        )

        self.agent = Agent(
            name="King Piece",
            model="gpt-4.1",
            instructions=self.prompt,
            output_type=KingState
        )

    async def call(self, debate: str, board_state: str):
        result = await Runner.run(self.agent, f"\nDebate State: {debate}\nBoard State: {board_state}")
        return result

async def main():
    king = KingPiece()
    result = await king.call("We should move forward", "Test")
    # print(result)
    return result.final_output


if __name__ == "__main__":
    print(asyncio.run(main()))

