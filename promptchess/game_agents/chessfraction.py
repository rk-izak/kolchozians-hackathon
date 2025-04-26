from agents import Agent, Runner
from pydantic import BaseModel


class DebateInput(BaseModel):
    debate_input: str


class ChessFaction:
    def __init__(self, model, piece_name, colour, behaviour_file, user_prompt='',):
        self.name = piece_name
        self.agent = None
        with open(behaviour_file, "r", encoding="utf8") as f:
            self.behaviour = f.readlines()
    
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
            f"You are the Lord-Commander of the {colour} {piece_name} Faction on an enchanted chessboard.\n"
            f"You have the following personality traits which define your character:\na{self.behaviour}\n"
            # — MISSION —
            f"Your sworn duty is to maneuver every {colour} {piece_name} under your banner.\n"
            "NEVER LEAVE THE CHARACTER."
            "In general, capital letters represent white pieces, and lowercase letters represent black pieces.\n"
            "Ensure you only move your own pieces according to available legal moves.\n"
            # — ROYAL DECREE (PLAYER INPUT) —
            "The King now delivers this decree from his honoured Court Advisor which you are obliged to follow alongside your own needs:\n"
            f"\"{user_prompt}\"\n"
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
        board_2d: str,
        legal_moves: list[str]
    ) -> DebateInput:
        agent_input = f'\nCurrent Board State:\nFEN: {board_fen}\n\n{board_2d} \n\nAvailable Moves:\n*{"\n*".join(legal_moves)}'
        run_result = await Runner.run(self.agent, agent_input)
        final_output = run_result.final_output_as(DebateInput)
        return final_output


    async def suggest_move(self, board):
        """
        Thin wrapper so GameState can call `await frac.suggest_move(board)`.
        """
        result = await self.call(board.get_fen(),
                                 board.get_board_2d_string(),
                                 board.get_legal_moves())
        return result.debate_input