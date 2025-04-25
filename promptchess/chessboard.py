import chess

from .utils import log_error, log_info, log_warning


class ChessBoard:
    """
    Manages the state and interactions of a chess game using python-chess,
    providing an interface suitable for LLM agent interaction.
    """

    def __init__(self, fen: str | None = None):
        """
        Initializes the chessboard.

        Args:
            fen: Optional FEN string to load a specific position.
                 If None, initializes to the standard starting position.
        """
        try:
            if fen:
                log_info(f'Initializing board from FEN: {fen}')
                self._board = chess.Board(fen)
            else:
                log_info('Initializing board to starting position.')
                self._board = chess.Board()
            log_info(f'ChessBoard initialized. FEN: {self.get_fen()}')
        except ValueError as e:
            log_error(f'Invalid FEN string provided: {fen} - {e}')
            log_info('Initializing with default board due to FEN error.')
            self._board = chess.Board()

    def get_fen(self) -> str:
        """Returns the current board state in FEN notation."""
        return self._board.fen()

    def get_legal_moves(self) -> list[str]:
        """Returns a list of legal moves in SAN notation for the current player."""
        if self._board.is_game_over():
            return []
        return [self._board.san(move) for move in self._board.legal_moves]

    def apply_move(self, move_san: str) -> tuple[bool, str]:
        """
        Attempts to apply a move to the board using SAN notation.
        Modifies the internal board state if the move is valid.

        Args:
            move_san: The move in Standard Algebraic Notation (e.g., 'e4').

        Returns:
            A tuple (success: bool, message: str) indicating if the move was applied.
        """
        if self._board.is_game_over():
            return False, 'Game is already over.'
        try:
            move = self._board.parse_san(move_san)
            self._board.push(move)
            log_info(f'Move applied: {move_san}. New FEN: {self.get_fen()}')
            return True, 'Move successful'
        except ValueError as e:
            error_message = f"Invalid or illegal move '{move_san}': {e}"
            log_warning(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"An unexpected error occurred trying to make move '{move_san}': {e}"
            log_error(error_message)
            return False, error_message

    def get_status(self) -> dict[str, object]:
        """Returns a dictionary describing the current game status."""
        status = {
            'is_game_over': self._board.is_game_over(),
            'result': self._board.result(),
            'is_checkmate': self._board.is_checkmate(),
            'is_stalemate': self._board.is_stalemate(),
            'is_insufficient_material': self._board.is_insufficient_material(),
            'is_seventyfive_moves': self._board.is_seventyfive_moves(),
            'is_fivefold_repetition': self._board.is_fivefold_repetition(),
            'is_check': self._board.is_check(),
            'winner': None,
        }

        if status['is_game_over']:
            result = status['result']
            if result == '1-0':
                status['winner'] = 'white'
            elif result == '0-1':
                status['winner'] = 'black'

        return status

    def is_game_over(self) -> bool:
        """Checks if the game has ended."""
        return self._board.is_game_over()

    def get_turn(self) -> str:
        """Returns whose turn it is ('white' or 'black')."""
        return 'white' if self._board.turn == chess.WHITE else 'black'

    def __str__(self) -> str:
        """Returns a simple string representation of the board."""
        return str(self._board)

    def print_board(self) -> None:
        """Prints the board to the console."""
        print(self._board)

    def piece_at(self, row, col) -> str | None:
        piece = self._board.piece_at(chess.square(col, row))
        if piece is not None:
            return str(piece)
        return None