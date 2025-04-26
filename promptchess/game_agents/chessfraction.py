from agents import Agent, Runner
from pydantic import BaseModel


class DebateInput(BaseModel):
    debate_input: str


class ChessFaction:
    def __init__(self, model, piece_name, colour, user_prompt=''):
        self.name = piece_name
        self.agent = None
    
        self.update_prompt(colour, piece_name, user_prompt)
        self.agent = Agent(
            name=piece_name,
            model=model,
            instructions=self.prompt,
            output_type=DebateInput,
        )

    def update_prompt(self, colour, piece_name, user_prompt):
        self.user_prompt = user_prompt
        self.prompt = (
            f'You are a in control of {colour} {piece_name} Faction in a game of Chess. '
            'Therefore, as their lord, you manage and are responsible for all of them.'
            f'{user_prompt}'
            'You report directly to the King Piece. Provide a useful suggestion in 2-3 sentences. '
        )
        if self.agent:
            self.agent.instructions = self.prompt

    def view_current_user_prompt(self):
        return self.user_prompt

    async def call(
        self,
        board_fen: str,
        board_2d: str
    ) -> DebateInput:
        agent_input = f'\nCurrent Board State:\nFEN: {board_fen}\n\n{board_2d}'
        run_result = await Runner.run(self.agent, agent_input)
        final_output = run_result.final_output_as(DebateInput)
        return final_output


    async def suggest_move(self, board):
        """
        Thin wrapper so GameState can call `await frac.suggest_move(board)`.
        """
        result = await self.call(board.get_fen(),
                                 board.get_board_2d_string())
        return result.debate_input