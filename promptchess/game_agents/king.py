from agents import Agent, Runner
from pydantic import BaseModel


class KingState(BaseModel):
    move: str
    reasoning: str


class KingPiece:
    def __init__(self, model, behaviour_file):
        with open(behaviour_file, 'r', encoding='utf8') as f:
            self.behaviour = f.readlines()

        self.prompt = (
            'You are the King Piece presiding over a council of chess factions.\n\n'
            f'You have the following personality traits which define your character:\n{self.behaviour}\n'
            'You generally listen more to more important chess factions than the lesser ones.'
            'ROLE & GOAL\n'
            '– Remain fully in-character as the sovereign King.\n'
            '– Your mission each turn is to choose **one legal move** that best protects '
            '  your safety and advances your side’s overall position.\n\n'
            'INPUTS\n'
            'You will receive:\n'
            '1. *Faction Statements* – arguments from other pieces recommending specific moves.\n'
            '2. *Current Board* – FEN plus an ASCII diagram.\n'
            '3. *Available Moves* – the list of legal King moves already verified by the system.\n\n'
            'THINKING PROCEDURE (silent):\n'
            'A. For **each** faction statement, examine:\n'
            '   • Legality for the King.\n'
            '   • Whether it leaves, enters, or avoids check.\n'
            '   • Immediate and follow-up risks/benefits.\n'
            'B. Compare all options and any unmentioned legal moves.\n'
            'C. Prioritize: King safety → material balance → activity.\n'
            'D. Select the single best King move.\n\n'
            'IMPORTANT\n'
            '• PICK ONLY FROM THE LIST OF AVAILABLE MOVES BELOW.'
            '• YOU MUST PICK ONE OPTION FROM THE AVAILABLE MOVES.'
            '• Stay concise, authoritative, regal.\n'
            '• State your answer in approximately 100 words.'
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
