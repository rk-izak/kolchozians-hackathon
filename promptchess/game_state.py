import chess # Need chess constants like chess.PAWN, chess.WHITE
from .chessboard import ChessBoard
from .game_agents.chessfraction import ChessFraction
from .game_agents.king import KingPiece, KingState
from .utils import log_info, log_warning, log_error


MODEL_PLACEHOLDER = "gpt-4o-mini"
# Map lowercase piece names to python-chess piece types
PIECE_TYPE_MAP = {
    'pawn': chess.PAWN,
    'knight': chess.KNIGHT,
    'bishop': chess.BISHOP,
    'rook': chess.ROOK,
    'queen': chess.QUEEN,
    # King is handled separately
}
FRACTION_PIECE_TYPES = list(PIECE_TYPE_MAP.keys())
PIECE_COLOURS = {'white': chess.WHITE, 'black': chess.BLACK}


class GameState:
    """
    Manages the overall state of the chess game, including the board,
    the AI agents representing piece fractions (tracking their presence),
    and the King agent for decisions.
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
                agent = ChessFraction(
                    model=MODEL_PLACEHOLDER,
                    piece_name=piece_key.capitalize(),
                    colour=color_name,
                    user_prompt=user_prompt
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
            kings[color_name] = KingPiece(model=MODEL_PLACEHOLDER)
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
            # Access the agent within the stored dictionary
            fraction_agent = self.fractions[color][piece_key]['agent']
            try:
                # Assuming update_prompt modifies the agent internally
                fraction_agent.update_prompt(color, piece_name.capitalize(), new_prompt)
                log_info(f"Updated prompt for {color} {piece_name} fraction.")
                return True
            except Exception as e:
                log_warning(f"Failed to update prompt for {color} {piece_name}: {e}")
                return False
        else:
            log_warning(f"Fraction {color} {piece_name} not found for prompt update.")
            return False

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

        Returns:
            A dictionary mapping piece type (lowercase) to its suggestion string.
        """
        current_turn = self.get_current_turn()
        board_fen = self.get_board_state()
        board_2d = self.board.get_board_2d_string() # Get 2D board string
        suggestions = {}

        log_info(f"Getting suggestions for active {current_turn} fractions...")
        active_fraction_count = 0
        # Iterate through the fraction data for the current player
        for piece_key, fraction_data in self.fractions[current_turn].items():
            # Only query active fractions
            if fraction_data['is_active']:
                active_fraction_count += 1
                fraction_agent = fraction_data['agent']
                try:
                    # Pass both FEN and 2D board string
                    result = await fraction_agent.call(board_fen, board_2d)
                    suggestions[piece_key] = result.debate_input
                    log_info(f"Suggestion from active {current_turn} {piece_key}: {result.debate_input}")
                except Exception as e:
                    log_warning(f"Error getting suggestion from active {current_turn} {piece_key}: {e}")
                    suggestions[piece_key] = f"Error fetching suggestion: {e}"

        log_info(f"Received suggestions for {current_turn} from {active_fraction_count} active fractions.")
        return suggestions

    async def decide_move(self) -> str | None:
        """
        Orchestrates getting fraction suggestions and using the King agent
        to decide the final move for the current player.

        Returns:
            The chosen move in SAN notation, or None if a decision cannot be made.
        """
        if self.is_game_over():
            log_info("Game is over, no move to decide.")
            return None

        current_turn = self.get_current_turn()
        log_info(f"Deciding move for {current_turn}...")

        # 1. Get suggestions from *active* fractions
        suggestions = await self.get_fraction_suggestions()

        # 2. Format suggestions into a debate string
        if suggestions:
             debate = "\n".join([f"{piece.capitalize()}: {suggestion}" for piece, suggestion in suggestions.items() if not suggestion.startswith('Error')]) # Exclude errors from debate?
        else:
             debate = "No suggestions available from active fractions."
        log_info(f"Formatted debate for {current_turn} King:\n{debate}")

        # 3. Get board state and legal moves
        board_fen = self.get_board_state()
        board_2d = self.board.get_board_2d_string() # Get 2D board string
        legal_moves = self.get_legal_moves()
        if not legal_moves:
             log_warning(f"No legal moves available for {current_turn}. Cannot decide move.")
             return None

        # 4. Call the King agent
        king_agent = self.kings[current_turn]
        try:
            # Pass both FEN and 2D board string to King agent
            king_decision = await king_agent.call(debate, board_fen, board_2d, legal_moves)
            chosen_move = king_decision.move
            log_info(f"{current_turn} King chose move: {chosen_move} (Reasoning: {king_decision.reasoning})")

            # 5. Basic validation
            if chosen_move not in legal_moves:
                log_warning(f"King chose an illegal move '{chosen_move}'. Legal: {legal_moves}. Trying to find a fallback.")
                if legal_moves:
                     fallback_move = legal_moves[0]
                     log_warning(f"Falling back to first legal move: {fallback_move}")
                     return fallback_move
                else:
                     return None

            return chosen_move

        except Exception as e:
            log_error(f"Error during King agent call for {current_turn}: {e}")
            if legal_moves:
                 log_warning("Falling back to first legal move due to King error.")
                 return legal_moves[0]
            return None

    def apply_move(self, move_san: str) -> tuple[bool, str]:
        """
        Applies a move to the board.

        Args:
            move_san: The move in Standard Algebraic Notation.

        Returns:
            A tuple (success: bool, message: str).
        """
        success, message = self.board.apply_move(move_san)
        if success:
            log_info(f"Move {move_san} applied successfully. Updating fraction status.")
            self._update_fraction_status()
        else:
            log_warning(f"Move {move_san} failed: {message}")
        return success, message

    def is_game_over(self) -> bool:
        """Checks if the game has ended."""
        return self.board.is_game_over()

    def print_board(self) -> None:
        """Prints the current board state to the console."""
        self.board.print_board()


async def main():
    game = GameState(white_user_prompt="Focus on controlling the center.")
    game.print_board()
    print(f"Turn: {game.get_current_turn()}")

    # Game loop example
    turn_count = 1
    max_turns = 100 # Add a max turn limit to prevent infinite loops
    while not game.is_game_over() and turn_count <= max_turns:
        print(f"\n--- {game.get_current_turn().upper()}'S TURN ({turn_count}) ---")
        chosen_move = await game.decide_move()

        if chosen_move:
            print(f"Chosen move: {chosen_move}")
            success, message = game.apply_move(chosen_move)
            if success:
                game.print_board()
                status = game.get_game_status()
                if status['is_checkmate']:
                    print(f"Checkmate! {status['winner']} wins.")
                    break
                elif status['is_stalemate']:
                    print("Stalemate!")
                    break
                elif status['is_insufficient_material']:
                    print("Draw by insufficient material.")
                    break
                elif status['is_seventyfive_moves']:
                    print("Draw by seventy-five moves rule.")
                    break
                elif status['is_fivefold_repetition']:
                    print("Draw by fivefold repetition.")
                    break
                elif status['is_check']:
                    print("Check!")
            else:
                print(f"!!! Failed to apply move '{chosen_move}': {message} !!!")
                # This indicates a bug either in King's choice or legal move generation
                break
        else:
            print("!!! Could not decide on a move. Stopping game. !!!")
            # This indicates a problem getting suggestions or with the King agent
            break
        turn_count += 1

    if turn_count > max_turns:
        print(f"\nGame stopped after reaching max turns ({max_turns}).")
    elif game.is_game_over() and not game.get_game_status().get('is_checkmate') and not game.get_game_status().get('is_stalemate'):
         print(f"\nGame over. Result: {game.get_game_status()['result']}")


if __name__ == "__main__":
    import asyncio
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())
