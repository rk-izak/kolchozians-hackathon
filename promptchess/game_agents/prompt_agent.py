from pathlib import Path
from typing import Dict, Optional

import chess
from agents import Agent, Runner
from pydantic import BaseModel, Field

from ..chessboard import PIECE_COLOURS, ChessBoard
from ..utils import log_error, log_info, log_warning


class SinglePromptUpdate(BaseModel):
    """Defines the output structure for updating a single fraction's prompt."""
    piece_type: str = Field(..., description="The lowercase name of the piece type to update (e.g., 'pawn', 'knight').")
    new_prompt: str = Field(..., description="The new concise prompt for the chosen piece type.")
    reasoning: str = Field(..., description="Brief explanation for choosing this piece type and prompt.")


class PromptAgent:
    """
    An LLM agent that plays PromptChess by generating a prompt update
    for a single chosen fraction each turn.
    """
    def __init__(self, color: str, model: str, behaviour_file: Path | str | None = None):
        """
        Initializes the PromptAgent.

        Args:
            color: The color the agent plays ('white' or 'black').
            model: The underlying LLM model identifier to use.
            behaviour_file: Optional path to a file defining agent's strategic style.
        """
        if color not in PIECE_COLOURS:
            raise ValueError(f"Invalid color specified: {color}")
        self.color = color
        self.color_const = PIECE_COLOURS[color]

        behaviour_text = ""
        if behaviour_file:
            try:
                with open(behaviour_file, "r") as f:
                    behaviour_text = f.read()
                log_info(f"Loaded behaviour for {self.color} PromptAgent from {behaviour_file}")
            except FileNotFoundError:
                log_warning(f"Behaviour file {behaviour_file} not found for {self.color} PromptAgent.")
            except Exception as e:
                log_warning(f"Error reading behaviour file {behaviour_file}: {e}")

        # Construct the detailed agent prompt - REVISED INPUTS/THINKING
        self.prompt = (
            f"You are a Chess Strategy AI playing PromptChess for the {self.color} side. Your task is to strategically update the prompt for **one** of your active piece fractions per turn.\n\n"
            "Your personality/strategy:\n"
            f"{behaviour_text if behaviour_text else 'You are a balanced and adaptable strategist.'}\n\n"
            "ROLE & GOAL:\n"
            f"– Analyze the current chess board state and the current prompts for your ({self.color}) side.\n"
            f"– Decide which **single active {self.color} fraction type** (pawn, knight, bishop, rook, or queen) would benefit most from a new instruction for this turn.\n"
            "– Generate a *new*, concise, and strategically effective prompt (1-2 sentences max) for **only that chosen piece type**.\n"
            f"– Provide a brief reasoning for your choice of piece type and the new prompt.\n"
            "– The prompts influence how fractions argue for moves in a later 'debate' phase.\n\n"
            "INPUTS:\n"
            "You will receive:\n"
            f"1. *Current Turn*: Whose turn it is.\n"
            f"2. *Board State*: FEN string and a 2D ASCII representation.\n"
            f"3. *Active {self.color} Pieces*: List of your piece types currently on the board.\n"
            f"4. *Current {self.color} Prompts*: The instructions currently assigned to your active piece types.\n"
            "\n"
            "THINKING PROCEDURE (silent):\n"
            f"A. Assess the overall board situation: material balance, king safety ({self.color} and opponent), central control, open lines, threats, key squares.\n"
            f"B. Review your own current prompts for all active pieces: Which seem outdated, ineffective, or less relevant to the current situation?\n"
            f"C. Identify the piece type where a new, targeted prompt could have the most positive impact on the upcoming move selection (e.g., coordinating an attack, shoring up defense, exploiting a weakness).\n"
            f"D. Formulate the *new*, concise prompt for the chosen piece type.\n"
            f"E. Write a brief justification for your choice.\n"
        )

        if Agent is None:
             log_error("Cannot initialize PromptAgent: 'agents' library components are missing.")
             self.agent = None
        else:
            self.agent = Agent(
                name=f'{self.color.capitalize()} PromptAgent',
                model=model,
                instructions=self.prompt,
                output_type=SinglePromptUpdate
            )
            log_info(f"Initialized {self.color} PromptAgent with model {model}.")


    async def decide_single_prompt_update(self, board: ChessBoard, current_prompts_self: Dict[str, str]) -> Optional[SinglePromptUpdate]:
        """
        Analyzes the board and current prompts to decide on a single prompt update.

        Args:
            board: The current ChessBoard object.
            current_prompts_self: Dict of current prompts for this agent's color.
        Returns:
            A SinglePromptUpdate object containing the chosen piece type, new prompt,
            and reasoning, or None if an error occurs or no update is decided.
        """
        if self.agent is None or Runner is None:
            log_error(f"PromptAgent ({self.color}) cannot generate prompts; 'agents' library missing.")
            return None

        log_info(f"PromptAgent ({self.color}) deciding single prompt update...")
        board_fen = board.get_fen()
        board_2d = board.get_board_2d_string()
        turn_color_str = "white" if board.get_turn_color() == chess.WHITE else "black"
        active_pieces_map = board.get_active_pieces().get(self.color, {})
        active_piece_types = [ptype for ptype, is_active in active_pieces_map.items() if is_active]

        if not active_piece_types:
            log_info(f"PromptAgent ({self.color}) has no active pieces to update.")
            return None

        # Filter current prompts to only include active types for clarity in the input
        filtered_prompts_self = {ptype: current_prompts_self.get(ptype, "N/A") for ptype in active_piece_types}

        # Format the input for the LLM agent
        agent_input = (
            f"Current Turn: {turn_color_str}\n\n"
            f"Board State:\nFEN: {board_fen}\n{board_2d}\n\n"
            f"Active {self.color} Pieces: {', '.join(active_piece_types)}\n\n"
            f"Current {self.color} Prompts:\n" +
            "\n".join([f"- {ptype.capitalize()}: {prompt}" for ptype, prompt in filtered_prompts_self.items()]) + "\n\n"
            f"Based on your analysis, provide the JSON output for the single prompt update (piece_type, new_prompt, reasoning)."
        )

        log_info(f"PromptAgent ({self.color}) input prepared for single update decision.")

        try:
            log_info(f"PromptAgent ({self.color}) calling Runner.run...")
            run_result = await Runner.run(
                self.agent,
                agent_input,
            )
            # Retrieve the output parsed as SinglePromptUpdate
            single_update = run_result.final_output_as(SinglePromptUpdate)

            if not single_update:
                 log_error(f"PromptAgent ({self.color}) received no output or failed parsing for single update.")
                 return None

            # Validate the chosen piece type
            if single_update.piece_type not in active_piece_types:
                log_warning(f"PromptAgent ({self.color}) chose an inactive or invalid piece type: '{single_update.piece_type}'. Active: {active_piece_types}")
                return None

            log_info(f"PromptAgent ({self.color}) successfully decided single update for '{single_update.piece_type}': '{single_update.new_prompt}'. Reasoning: {single_update.reasoning}")
            return single_update

        except Exception as e:
            log_error(f"PromptAgent ({self.color}) failed during single prompt update decision: {e}", exc_info=True)
            return None
