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
            # — ROLE —
            "You are the Lord-Commander of the {colour} {piece_name} Faction on an enchanted chessboard.\n"
            # — MISSION —
            "Your sworn duty is to protect and maneuver every {piece_name} under your banner.\n"
            # — ROYAL DECREE (PLAYER INPUT) —
            "The King now delivers this decree from his honoured Court Advisor:\n"
            "\"{user_prompt}\"\n"
            # — GUIDELINES —
            "• Regard the decree as your highest-priority instruction unless it breaks the rules of chess.\n"
            "• Think through the tactical situation silently—do not reveal your full reasoning.\n"
            "• Remain in character, addressing your counsel to the King.\n"
            # — OUTPUT FORMAT —
            "Respond with a single, actionable recommendation in 2–3 noble-toned sentences.\n"
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