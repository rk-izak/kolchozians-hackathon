from pathlib import Path
from typing import Dict

import chess
from agents import Agent, Runner
from pydantic import BaseModel

from ..chessboard import FRACTION_PIECE_TYPES, PIECE_COLOURS, ChessBoard
from ..utils import log_info, log_warning, log_error


class PromptSet(BaseModel):
    prompts: Dict[str, str]


class PromptAgent:
    """
    An LLM agent that plays PromptChess by generating prompts for its fractions
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

        # Construct the detailed agent prompt
        self.prompt = (
            f"You are a Chess Strategy AI that generates tactical prompts for individual chess piece types (fractions) of the {self.color} side in a game called PromptChess.\n\n"
            "Your personality/strategy:\n"
            f"{behaviour_text if behaviour_text else 'You are a balanced and adaptable strategist.'}\n\n"
            "ROLE & GOAL:\n"
            f"– Analyze the current chess board state and the current prompts for both {self.color} (your side) and the opponent.\n"
            f"– Your goal is to generate a *new*, concise, and strategically effective prompt for **each** of the currently active {self.color} fraction types (pawn, knight, bishop, rook, queen).\n"
            "– These prompts will guide the individual fractions in their 'debate' phase before a final move is selected by the King.\n"
            "– The prompts should reflect a coherent strategy for the current turn, considering board control, piece development, king safety, and potential threats/opportunities.\n\n"
            "INPUTS:\n"
            "You will receive:\n"
            f"1. *Current Turn*: Whose turn it is.\n"
            f"2. *Board State*: FEN string and a 2D ASCII representation.\n"
            f"3. *Active {self.color} Pieces*: List of your piece types currently on the board.\n"
            f"4. *Current {self.color} Prompts*: The instructions currently assigned to your active piece types.\n"
            f"5. *Current Opponent Prompts*: The instructions currently assigned to the opponent's active piece types (for context).\n\n"
            "THINKING PROCEDURE (silent):\n"
            f"A. Assess the overall board situation: material balance, king safety ({self.color} and opponent), central control, open lines, threats.\n"
            f"B. Analyze the opponent's current prompts: What might their strategy be? What threats do their prompts suggest?\n"
            f"C. Review your own current prompts: Are they still relevant? Are they leading to good suggestions?\n"
            f"D. Formulate a strategic plan for {self.color} for this turn.\n"
            f"E. For **each** active {self.color} piece type (pawn, knight, bishop, rook, queen), generate a *new*, concise prompt (1-2 sentences max) that directs it according to your strategic plan.\n"
            "   – Example Pawn Prompt: 'Focus on controlling d5 and supporting the knight attack.'\n"
            "   – Example Knight Prompt: 'Find an outpost on f5 or attack the weak pawn on c6.'\n\n"
            "OUTPUT FORMAT:\n"
            "– Provide your response as a JSON object where keys are the lowercase piece types ('pawn', 'knight', 'bishop', 'rook', 'queen') and values are the corresponding new prompt strings.\n"
            f"– **Only include entries for the active {self.color} piece types listed in the input.**\n"
            "– Example Output: ```json\n{\"pawn\": \"Advance on the kingside.\", \"knight\": \"Target the f7 square.\"}\n```\n"
        )

        self.agent = Agent(
            name=f'{self.color.capitalize()} PromptAgent',
            model=model,
            instructions=self.prompt,
            output_type=PromptSet
        )
        log_info(f"Initialized {self.color} PromptAgent with model {model}.")


    async def generate_prompts(self, board: ChessBoard, current_prompts_self: Dict[str, str], current_prompts_opponent: Dict[str, str]) -> Dict[str, str]:
        """
        Analyzes the board and current prompts to generate new prompts for active fractions.

        Args:
            board: The current ChessBoard object.
            current_prompts_self: Dict of current prompts for this agent's color.
            current_prompts_opponent: Dict of current prompts for the opponent's color.

        Returns:
            A dictionary mapping active piece type to its newly generated prompt string.
        """
        if self.agent is None or Runner is None:
            log_error(f"PromptAgent ({self.color}) cannot generate prompts; 'agents' library missing.")
            return {} # Return empty dict if agent wasn't initialized

        log_info(f"PromptAgent ({self.color}) generating prompts...")
        board_fen = board.get_fen()
        board_2d = board.get_board_2d_string()
        turn_color_str = "white" if board.get_turn_color() == chess.WHITE else "black"
        active_pieces_map = board.get_active_pieces().get(self.color, {})
        active_piece_types = [ptype for ptype, is_active in active_pieces_map.items() if is_active]

        # Filter current prompts to only include active types for clarity in the input
        filtered_prompts_self = {ptype: current_prompts_self.get(ptype, "N/A") for ptype in active_piece_types}
        # Opponent prompts can be passed entirely for context
        opponent_color = 'black' if self.color == 'white' else 'white'
        active_opponent_map = board.get_active_pieces().get(opponent_color, {})
        filtered_prompts_opponent = {ptype: current_prompts_opponent.get(ptype, "N/A")
                                      for ptype, is_active in active_opponent_map.items() if is_active}


        # Format the input for the LLM agent
        agent_input = (
            f"Current Turn: {turn_color_str}\n\n"
            f"Board State:\nFEN: {board_fen}\n{board_2d}\n\n"
            f"Active {self.color} Pieces: {', '.join(active_piece_types) if active_piece_types else 'None'}\n\n"
            f"Current {self.color} Prompts:\n" +
            "\n".join([f"- {ptype.capitalize()}: {prompt}" for ptype, prompt in filtered_prompts_self.items()]) + "\n\n"
            f"Current Opponent ({opponent_color}) Prompts:\n" +
            "\n".join([f"- {ptype.capitalize()}: {prompt}" for ptype, prompt in filtered_prompts_opponent.items()]) + "\n\n"
            f"Generate the new JSON prompts for the active {self.color} pieces based on the analysis."
        )

        log_info(f"PromptAgent ({self.color}) input prepared:\n{agent_input}")

        try:
            # Run the agent using the 'agents' library Runner
            run_result = await Runner.run(
                self.agent,
                agent_input,
            )
            # Assuming run_result.final_output gives the dictionary directly or a JSON string
            # If it requires parsing via a Pydantic model, use:
            # final_output = run_result.final_output_as(PromptSet)
            # new_prompts = final_output.prompts
            new_prompts = run_result.final_output

            if not isinstance(new_prompts, dict):
                 log_warning(f"PromptAgent ({self.color}) received non-dict output: {type(new_prompts)}. Attempting to parse if string.")
                 # Attempt to parse if it looks like JSON string (basic check)
                 if isinstance(new_prompts, str) and new_prompts.strip().startswith('{'):
                     import json
                     try:
                         new_prompts = json.loads(new_prompts)
                         if not isinstance(new_prompts, dict):
                             raise ValueError("Parsed JSON is not a dictionary.")
                     except (json.JSONDecodeError, ValueError) as e:
                         log_error(f"PromptAgent ({self.color}) failed to parse output as JSON dictionary: {e}\nOutput was: {new_prompts}")
                         return {} # Failed parsing
                 else:
                     log_error(f"PromptAgent ({self.color}) received unexpected output format.")
                     return {} # Unexpected format


            log_info(f"PromptAgent ({self.color}) successfully generated prompts: {new_prompts}")
            # Optional: Validate that keys are valid piece types and values are strings
            validated_prompts = {}
            for key, value in new_prompts.items():
                if key in FRACTION_PIECE_TYPES and isinstance(value, str):
                     validated_prompts[key] = value
                else:
                    log_warning(f"PromptAgent ({self.color}) generated invalid entry: key='{key}', value_type='{type(value)}'. Skipping.")
            return validated_prompts

        except Exception as e:
            log_error(f"PromptAgent ({self.color}) failed during generation: {e}", exc_info=True)
            return {} # Return empty on error


# Update Example Usage
async def test_prompt_agent():
    # Requires GameState to get current prompts easily
    # Let's simulate it for now
    from ..game_state import GameState  # Import here for testing scope
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Initialize GameState to get initial prompts
    game = GameState()
    board_obj = game.board

    # Create agents (assuming GEMINI_MODEL is defined or use a placeholder)
    try:
        white_agent = PromptAgent(color='white', model="gemini-1.5-flash-latest", behaviour_file="behaviours/balanced.txt") # Example model
        black_agent = PromptAgent(color='black', model="gemini-1.5-flash-latest", behaviour_file="behaviours/aggressive.txt")
    except NameError:
         print("Agent or Runner likely missing, cannot run test.")
         return
    except Exception as e:
        print(f"Error initializing agents: {e}")
        return


    # --- Turn 1 (White) ---
    print("\n--- Turn 1: White Agent Deciding Prompts ---")
    # Get current prompts (initially default/empty from GameState setup)
    current_prompts_w = {ptype: game.get_fraction_user_prompt('white', ptype) or "" for ptype in FRACTION_PIECE_TYPES}
    current_prompts_b = {ptype: game.get_fraction_user_prompt('black', ptype) or "" for ptype in FRACTION_PIECE_TYPES}

    new_prompts_white = await white_agent.generate_prompts(board_obj, current_prompts_w, current_prompts_b)
    print("White Agent Generated Prompts:")
    for piece, prompt in new_prompts_white.items():
        print(f"  {piece.capitalize()}: {prompt}")
        # Update GameState with new prompts
        game.update_fraction_prompt('white', piece, prompt)

    # Assume White makes a move based on these prompts (using game.decide_move logic)
    # Simulate move for testing prompt generation
    move_made = "e2e4"
    success, _ = game.apply_move(move_made)
    if not success: print(f"Failed to apply simulated move {move_made}"); return
    print(f"\nSimulated White Move: {move_made}")
    game.print_board()


    # --- Turn 2 (Black) ---
    print("\n--- Turn 2: Black Agent Deciding Prompts ---")
    # Get current prompts (White's were updated, Black's are still initial)
    current_prompts_w = {ptype: game.get_fraction_user_prompt('white', ptype) or "" for ptype in FRACTION_PIECE_TYPES}
    current_prompts_b = {ptype: game.get_fraction_user_prompt('black', ptype) or "" for ptype in FRACTION_PIECE_TYPES}

    new_prompts_black = await black_agent.generate_prompts(board_obj, current_prompts_b, current_prompts_w)
    print("Black Agent Generated Prompts:")
    for piece, prompt in new_prompts_black.items():
        print(f"  {piece.capitalize()}: {prompt}")
        game.update_fraction_prompt('black', piece, prompt)

    # Assume Black makes move...


if __name__ == "__main__":
    import asyncio
    import logging

    # Ensure game_state methods used in test are available
    # Add basic config for logging used within the class
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Assuming the 'agents' library is structured such that Agent/Runner are available
    if Agent is not None and Runner is not None:
         asyncio.run(test_prompt_agent())
    else:
        print("Cannot run test_prompt_agent as Agent/Runner components are missing.")
