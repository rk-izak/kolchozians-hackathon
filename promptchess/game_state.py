import chess # Need chess constants like chess.PAWN, chess.WHITE
import asyncio # Added for potential async operations if needed elsewhere

from .chessboard import ChessBoard
from .game_agents.evaluator import Evaluator
from .game_agents.chessfraction import ChessFaction
# *** ADDED Jester Import ***
from .game_agents.jester import ChessJester, JesterState
from .game_agents.king import KingPiece, KingState
from .utils import log_info, log_warning, log_error
from pathlib import Path
from typing import Optional # Added for type hinting


# MODEL_PLACEHOLDER = "gpt-4o-mini"
SMART_MODEL = "o3-2025-04-16"
BALANCED_MODEL = "gpt-4.1-2025-04-14"
EFFICIENT_MODEL = "o4-mini-2025-04-16"

# Map lowercase piece names to python-chess piece types
PIECE_TYPE_MAP = {
    'pawn': chess.PAWN,
    'knight': chess.KNIGHT,
    'bishop': chess.BISHOP,
    'rook': chess.ROOK,
    'queen': chess.QUEEN,
    # King is handled separately
}
SHORT_PIECE_MAP = {
    'p': 'pawn',
    'n': 'knight',
    'b': 'bishop',
    'r': 'rook',
    'q': 'queen'
}
FRACTION_PIECE_TYPES = list(PIECE_TYPE_MAP.keys())
PIECE_COLOURS = {'white': chess.WHITE, 'black': chess.BLACK}


class GameState:
    """
    Manages the overall state of the chess game, including the board,
    the AI agents representing piece fractions (tracking their presence),
    the King agent for decisions, the Evaluator, and the Jester.
    """

    def __init__(self, fen: str | None = None, white_user_prompt: str = '', black_user_prompt: str = ''):
        """
        Initializes the game state.

        Args:
            fen: Optional FEN string to load a specific board position.
            white_user_prompt: Initial custom prompt instructions for the white fractions.
            black_user_prompt: Initial custom prompt instructions for the black fractions.
        """
        log_info("Initializing GameState...")
        self.board = ChessBoard(fen)
        # Initialize fractions with agent and active status
        self.fractions = self._initialize_fractions(white_user_prompt, black_user_prompt)
        self.kings = self._initialize_kings()
        self.evaluator = Evaluator(model=BALANCED_MODEL)
        # *** ADDED Jester Initialization ***
        self.jester = ChessJester(model=BALANCED_MODEL) # Using BALANCED_MODEL, adjust if needed
        self.last_jester_commentary: Optional[JesterState] = None # To store the last comment
        self.decided_move: Optional[str] = None # Store the move decided by the King

        self._update_fraction_status() # Set initial active status based on board
        log_info("GameState initialized.")

    def _initialize_fractions(self, white_user_prompt: str, black_user_prompt: str) -> dict:
        """Initializes ChessFraction agents, storing them with an 'is_active' flag."""
        log_info("Initializing fractions...")
        fractions_data = {'white': {}, 'black': {}}

        for color_name, color_const in PIECE_COLOURS.items():
            user_prompt = white_user_prompt if color_name == 'white' else black_user_prompt
            fractions_data[color_name] = {}
            for piece_key in FRACTION_PIECE_TYPES:
                fraction_name = f"{color_name}_{piece_key}"
                agent = ChessFaction(
                    model=EFFICIENT_MODEL,
                    piece_name=piece_key.capitalize(),
                    colour=color_name,
                    user_prompt=user_prompt,
                    behaviour_file=Path("behaviours") / f"{piece_key}.txt"
                )
                # Store agent and initial active status (will be updated shortly)
                fractions_data[color_name][piece_key] = {'agent': agent, 'is_active': True}
                log_info(f"Initialized fraction agent: {fraction_name}")

        log_info("Fraction agents initialized.")
        return fractions_data

    def _initialize_kings(self) -> dict[str, KingPiece]:
        """Initializes the KingPiece agents for both colors."""
        log_info("Initializing King agents...")
        kings = {}
        for color_name in PIECE_COLOURS.keys():
            kings[color_name] = KingPiece(model=SMART_MODEL)
            log_info(f"Initialized {color_name} King agent.")
        log_info("King agents initialized.")
        return kings

    def _update_fraction_status(self) -> None:
        """Gets active piece status from the board and updates fraction statuses."""
        log_info("Updating fraction active status...")
        active_pieces_on_board = self.board.get_active_pieces()

        updated_count = 0
        deactivated_count = 0

        # Iterate through our stored fractions and update based on board status
        for color_name, fractions_for_color in self.fractions.items():
            if color_name not in active_pieces_on_board:
                log_warning(f"Color '{color_name}' not found in board active pieces status. Skipping.")
                continue

            board_status_for_color = active_pieces_on_board[color_name]
            for piece_key, fraction_data in fractions_for_color.items():
                # Check if this piece type exists in the status from the board
                is_now_active = board_status_for_color.get(piece_key, False)
                was_active = fraction_data['is_active']

                if was_active != is_now_active:
                    fraction_data['is_active'] = is_now_active
                    status_change = "activated" if is_now_active else "deactivated"
                    log_info(f"Fraction {color_name} {piece_key} {status_change}.")
                    updated_count += 1
                    if not is_now_active:
                        deactivated_count += 1

        log_info(f"Fraction status update complete. {updated_count} status changes ({deactivated_count} deactivated).")

    def update_fraction_prompt(self, color: str, piece_name: str, new_prompt: str) -> bool:
        """
        Updates the user prompt for a specific fraction.

        Args:
            color: The color of the fraction ('white' or 'black').
            piece_name: The name of the piece type (e.g., 'pawn', 'knight'). Excludes 'king'.
            new_prompt: The new user prompt string.

        Returns:
            True if the fraction was found and updated, False otherwise.
        """
        piece_key = piece_name.lower()
        if piece_key == 'king':
            log_warning("Cannot update prompt for King fraction; use King agent methods if needed.")
            return False
        if color in self.fractions and piece_key in self.fractions[color]:
            fraction_agent = self.fractions[color][piece_key]['agent']
            try:
                # Assuming ChessFaction has an update_prompt method similar to this:
                # fraction_agent.update_prompt(new_prompt) # Adjust if method signature differs
                # Let's assume the agent has a user_prompt attribute directly for simplicity if update_prompt doesn't exist
                fraction_agent.user_prompt = new_prompt # Or call the actual update method
                log_info(f"Updated prompt for {color} {piece_name} fraction.")
                return True
            except Exception as e:
                log_warning(f"Failed to update prompt for {color} {piece_name}: {e}")
                return False
        else:
            log_warning(f"Fraction {color} {piece_name} not found for prompt update.")
            return False

    def get_fraction_user_prompt(self, color: str, piece_name: str) -> str | None:
        """
        Retrieves the current user_prompt for a specific fraction.

        Args:
            color: The color of the fraction ('white' or 'black').
            piece_name: The name of the piece type (e.g., 'pawn', 'knight').

        Returns:
            The current user_prompt string, or None if the fraction is not found.
        """
        piece_key = piece_name.lower()
        if piece_key == 'king':
            log_warning("King piece does not have a standard user prompt in this structure.")
            return None

        if color in self.fractions and piece_key in self.fractions[color]:
            fraction_agent = self.fractions[color][piece_key]['agent']
            # Assuming the agent has a user_prompt attribute or a getter method
            return getattr(fraction_agent, 'user_prompt', None) # Adjust if needed
        else:
            log_warning(f"Fraction {color} {piece_name} not found.")
            return None

    def get_board_state(self) -> str:
        """Returns the current board state in FEN notation."""
        return self.board.get_fen()

    def get_current_turn(self) -> str:
        """Returns the color of the player whose turn it is."""
        return 'white' if self.board._board.turn == chess.WHITE else 'black'

    def get_game_status(self) -> dict[str, object]:
        """Returns the current status of the game (over, check, winner, etc.)."""
        return self.board.get_status()

    def get_legal_moves(self) -> list[str]:
        """Returns a list of legal moves for the current player."""
        return self.board.get_legal_moves()

    async def get_fraction_suggestions(self) -> dict[str, str]:
        """
        Gets move suggestions from the fractions of the current player.
        DEPRECATED in favor of the logic within decide_move? Keep if used elsewhere.
        If decide_move handles this, this method might be redundant for the main flow.
        """
        current_turn = self.get_current_turn()
        board_fen = self.get_board_state()
        board_2d = self.board.get_board_2d_string() # Get 2D board string
        suggestions = {}

        log_info(f"Getting suggestions for active {current_turn} fractions...")
        active_fraction_count = 0
        # This call assumes ChessFaction.call exists and returns an object with 'debate_input'
        # Adjust if the actual method/return structure is different (e.g., using suggest_move)
        for piece_key, fraction_data in self.fractions[current_turn].items():
            if fraction_data['is_active']:
                active_fraction_count += 1
                fraction_agent = fraction_data['agent']
                try:
                    # Using suggest_move as seen in decide_move, adapt if 'call' is preferred
                    result_text = await fraction_agent.suggest_move(self.board) # Assuming suggest_move returns string
                    suggestions[piece_key] = result_text
                    log_info(f"Suggestion from active {current_turn} {piece_key}: {result_text}")
                except Exception as e:
                    log_warning(f"Error getting suggestion from active {current_turn} {piece_key}: {e}")
                    suggestions[piece_key] = f"Error fetching suggestion: {e}"

        log_info(f"Received suggestions for {current_turn} from {active_fraction_count} active fractions.")
        return suggestions

    def get_active_fractions(self, colour: str | None = None) -> list[ChessFaction]:
        """
        Return a list with the *agents* of all fractions that are still on
        the board for the requested colour.
        """
        if colour is None:
            colour = self.get_current_turn()

        if colour not in self.fractions:
            return []

        active = []
        for piece_key, data in self.fractions[colour].items():
            if data["is_active"]:
                active.append(data["agent"])
        return active

    async def decide_move(self):
        """
        Async-generator version of move decision process.

        Yields:
            ("debate",  <str>)         – more text to append to the debate
            ("status",  <str>)         – e.g. "analysing king reply ..."
            ("move",    <san_move>)    – final choice, search finished
        """

        if self.is_game_over():
            yield ("status", "Game is already over.")
            return

        turn = self.get_current_turn()
        yield ("status", f"## Deciding move for {turn} …")

        # ── 1. Ask every *active* fraction, stream its answer ─────────
        debate_lines = []
        active_fractions = self.get_active_fractions()

        for frac in active_fractions:
            # Use suggest_move as indicated, assuming it takes the board object
            # and returns a string suggestion.
            try:
                # Ensure the agent has the 'suggest_move' method as used here.
                # If not, adapt to the correct method (e.g., 'call').
                if hasattr(frac, 'suggest_move') and callable(frac.suggest_move):
                     sugg = await frac.suggest_move(self.board) # Pass board object if needed
                # Fallback or alternative if 'call' is the standard interface
                elif hasattr(frac, 'call') and callable(frac.call):
                    board_fen = self.get_board_state()
                    board_2d = self.board.get_board_2d_string()
                    # Assuming call returns an object with debate_input
                    call_result = await frac.call(board_fen, board_2d)
                    sugg = getattr(call_result, 'debate_input', "Suggestion format error.")
                else:
                    sugg = f"Agent {frac.name} has no recognized suggestion method."
                    log_warning(sugg)

            except Exception as e:
                log_error(f"Error getting suggestion from {frac.name}: {e}")
                sugg = f"Error: {e}"

            # Make sure frac.name exists and piece_name is capitalized correctly
            frac_display_name = getattr(frac, 'piece_name', getattr(frac, 'name', 'Unknown Fraction')).capitalize()
            line = f"### {frac_display_name}: {sugg}"
            debate_lines.append(line)
            # Yield formatted for UI display
            yield ("debate", f"__{frac_display_name}__: {sugg}\n\n")


        debate_text = "\n".join(debate_lines)
        yield ("status", "## King is thinking …")

        king = self.kings[turn]
        legal_moves = self.get_legal_moves()

        # Ensure King's call method signature matches
        decision = await king.call(
            debate_text,
            self.get_board_state(),             # FEN
            self.board.get_board_2d_string(),
            legal_moves # Pass the list of legal moves
        )
        # Assuming decision has 'reasoning' and 'move' attributes
        yield ("debate", f"\n**King's Decision:**\n{getattr(decision, 'reasoning', 'No reasoning provided.')}\n")

        chosen_move = getattr(decision, 'move', None)
        self.decided_move = chosen_move # Store the decided move

        # Basic legality check
        if not chosen_move or chosen_move not in legal_moves:
            yield ("status", f"King chose illegal/invalid move ('{chosen_move}'). Choosing first legal move.")
            log_warning(f"King chose illegal/invalid move ('{chosen_move}'). Legal: {legal_moves}")
            if not legal_moves:
                 yield ("status", "No legal moves available! Game might be over.")
                 # Handle this case - maybe yield a special status or raise error?
                 # For now, we won't yield a move if none are legal.
                 return # Stop the generator
            chosen_move = legal_moves[0]
            self.decided_move = chosen_move # Update stored move

        yield ("move", chosen_move) # <── final yield

    # *** MODIFIED apply_move TO BE ASYNC and CALL JESTER ***
    async def apply_move(self, move_san: str) -> tuple[bool, str]:
        """
        Applies a move to the board, updates fraction status, and gets Jester commentary.

        Args:
            move_san: The move in Standard Algebraic Notation.

        Returns:
            A tuple (success: bool, message: str).
        """
        # Reset jester commentary before applying
        self.last_jester_commentary = None

        success, message = self.board.apply_move(move_san)
        if success:
            log_info(f"Move {move_san} applied successfully. Updating fraction status.")
            self._update_fraction_status()

            # *** Call Jester after successful move ***
            try:
                board_fen = self.get_board_state()
                board_2d = self.board.get_board_2d_string()
                log_info("Calling Jester for commentary...")
                self.last_jester_commentary = await self.jester.call(board_fen, board_2d)
                log_info(f"Jester commented: {self.last_jester_commentary.judgement.value} - '{self.last_jester_commentary.joke_output}'")
            except Exception as e:
                log_error(f"Error getting Jester commentary: {e}")
                self.last_jester_commentary = None # Ensure it's None on error

        else:
            log_warning(f"Move {move_san} failed: {message}")
        return success, message

    # *** ADDED: Method to get last jester commentary ***
    def get_last_jester_commentary(self) -> JesterState | None:
        """Returns the JesterState from the last move, if available."""
        return self.last_jester_commentary

    # *** ADDED: Method to clear last jester commentary ***
    def clear_last_jester_commentary(self):
         """Clears the last commentary (e.g., after the UI displays it)."""
         self.last_jester_commentary = None
         log_info("Cleared last Jester commentary.")

    async def evaluate_board(self):
        """Calls the evaluator and returns a clamped evaluation score."""
        try:
            evaluation_result = await self.evaluator.call(
                self.get_board_state(),
                self.board.get_board_2d_string(),
            )
            # Assuming the result object has an 'eval' attribute that's convertible to int
            evaluation = int(getattr(evaluation_result, 'eval', 0))
            evaluation = min(evaluation, 10)
            evaluation = max(evaluation, -10)
            # No need to round if we already cast to int
            return evaluation # Return int directly
        except Exception as e:
            log_error(f"Error during board evaluation: {e}")
            return 0 # Return neutral evaluation on error


    def is_game_over(self) -> bool:
        """Checks if the game has ended."""
        return self.board.is_game_over()

    def print_board(self) -> None:
        """Prints the current board state to the console."""
        self.board.print_board()

# Example main loop (needs adjustments for async apply_move and decide_move generator)
async def main():
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    game = GameState(white_user_prompt="Focus on controlling the center.")
    game.print_board()
    print(f"Turn: {game.get_current_turn()}")

    # Game loop example
    turn_count = 1
    max_turns = 100 # Add a max turn limit
    while not game.is_game_over() and turn_count <= max_turns:
        print(f"\n--- {game.get_current_turn().upper()}'S TURN ({turn_count}) ---")

        chosen_move = None
        # Use async for to handle the generator
        async for kind, payload in game.decide_move():
            if kind == "debate":
                print(f"Debate: {payload.strip()}")
            elif kind == "status":
                print(f"Status: {payload}")
            elif kind == "move":
                chosen_move = payload
                print(f"King decided move: {chosen_move}")
                break # Exit the generator loop once move is decided

        if chosen_move:
            # Await the async apply_move
            success, message = await game.apply_move(chosen_move)
            if success:
                game.print_board()
                # Check for jester comment (optional here, primarily for UI)
                jester_comment = game.get_last_jester_commentary()
                if jester_comment:
                    print(f"Jester: [{jester_comment.judgement.value}] {jester_comment.joke_output}")
                    game.clear_last_jester_commentary() # Clear after printing

                status = game.get_game_status()
                if status.get('is_game_over'):
                    print(f"\nGame Over!")
                    if status.get('is_checkmate'):
                         print(f"Checkmate! Winner: {status.get('winner', 'Unknown')}")
                    elif status.get('is_stalemate'):
                         print("Result: Stalemate")
                    elif status.get('is_insufficient_material'):
                         print("Result: Draw by insufficient material")
                    # Add other draw conditions if needed
                    else:
                         # Use the outcome() method for more robust result determination
                         outcome = game.board._board.outcome()
                         if outcome:
                             print(f"Result: {outcome.termination.name}, Winner: {outcome.winner}")
                         else:
                             print(f"Result: {status.get('result', 'Unknown reason')}") # Fallback
                    break
                elif status.get('is_check'):
                    print("Check!")
            else:
                print(f"!!! Failed to apply move '{chosen_move}': {message} !!!")
                # This might indicate a bug in King's choice or legal move generation fallback
                break
        else:
            print("!!! Could not decide on a move. Stopping game. !!!")
            # This indicates a problem getting suggestions or with the King agent
            break
        turn_count += 1

    if turn_count > max_turns:
        print(f"\nGame stopped after reaching max turns ({max_turns}).")
    elif not game.is_game_over():
         print("\nGame stopped for other reasons.")


if __name__ == "__main__":
    # Main execution remains the same
    asyncio.run(main())