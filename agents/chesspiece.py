from pydantic import BaseModel
from agents import Agent, Runner
import asyncio

class DebateInput(BaseModel):
    debate_input: str

class ChessPiece:
    def __init__(self, model, piece_name):
        self.prompt = (
            f"You are a {piece_name} Piece in a game of Chess. "
            "You report directly to the King Piece. "
            "Your task is to first decide which piece should be moved and to which position based on the current board state. "
            "After you make that decision, write a short (1-2 sentences) recommendation to the King Piece trying influence his decision. "
            "You must ensure your move is legal for a current board state and chess piece. "
        )

        self.agent = Agent(
            name=piece_name,
            model=model,
            instructions=self.prompt,
            output_type=DebateInput,
        )
    
    async def call(self, own_position: str, board_state: str):
        result = await Runner.run(self.agent, f"\nYour Position: {own_position}\nBoard State: {board_state}")
        return result

async def main():
    piece = ChessPiece(model='gpt-4.1-nano', piece_name='Bishop')
    result = await piece.call("E5", "Test")
    # print(result)
    return result.final_output


if __name__ == "__main__":
    print(asyncio.run(main()))
