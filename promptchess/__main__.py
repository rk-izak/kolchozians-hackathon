import gradio as gr
from functools import partial
import asyncio # *** ADDED for sleep ***

# *** Import JesterState for type hints if needed, and GameState components ***
from .game_state import GameState, SHORT_PIECE_MAP, JesterState # Assuming JesterState is needed

PIECES = {
    'p': '♟', 'r': '♜', 'b': '♝',
    'q': '♛', 'k': '♚', 'n': '♞',
}

CSS = """
.cell {
    width: 70px !important;
    height: 70px !important;
    font-size: 48px !important;
    padding: 0 !important;
    line-height: 70px !important; /* Better vertical alignment */
    text-align: center; /* Center pieces */
}
.cell-white-fg { color: #DDDDDD; }
.cell-white-fg textarea { color: #DDDDDD; }
.cell-white-bg { background-color: #BBBBA0; }
.cell-black-fg { color: #111111; }
.cell-black-fg textarea { color: #111111; }
.cell-black-bg { background-color: #769455; }
.cell-border { border: 5px solid red !important; } /* Ensure border overrides */

.figure-img textarea {
    font-size: 48px !important; /* Adjusted size */
    text-align: center;
    line-height: 70px !important;
}

button.cell:disabled,
.gr-button:disabled.cell {
    opacity: 0.7 !important;
    cursor: default !important;
}

.rank-file-label {
    width: 70px;
    height: 70px;
    font-size: 20px; /* Smaller labels */
    text-align: center;
    line-height: 70px;
    padding: 0 !important;
    color: #555; /* Dimmer color */
}
.rank-file-label p { margin: 0; } /* Remove default paragraph margin */

.thermo { width: 100%; }

/* *** ADDED styles for Jester *** */
.jester-box {
    border: 2px dashed purple;
    padding: 10px;
    border-radius: 5px;
    margin-top: 10px;
    background-color: #f0e6ff; /* Light purple background */
}
.jester-box .gr-markdown p { /* Style text inside jester markdown */
    margin: 0;
    padding: 2px 0;
    font-style: italic;
    color: #330066; /* Darker purple text */
}
.jester-box .gr-progress { /* Style progress bar */
    height: 10px !important;
}

"""


GAME = GameState()

def get_cell_properties(rank: int, file: int, piece: str | None, selected_square: tuple[int, int] | None = None) -> dict:
    """ Gets Gradio Button properties based on board state and selection """
    square = (rank, file)
    is_white_bg = (file + rank) % 2 != 0 # Adjusted logic based on standard board a1=dark
    bg_class = "cell-white-bg" if is_white_bg else "cell-black-bg"
    classes = ["cell", bg_class]

    if piece is not None:
        fg_class = "cell-white-fg" if piece.isupper() else "cell-black-fg"
        classes.append(fg_class)

    # Highlight selected square
    if selected_square is not None and square == selected_square:
         classes.append("cell-border")

    # Determine interactivity: only pieces of the current turn (excluding King)
    interactive = False
    if piece is not None and piece.lower() != 'k': # Kings cannot be selected for prompts
        is_white_turn = GAME.get_current_turn() == 'white'
        is_black_turn = not is_white_turn
        if (is_white_turn and piece.isupper()) or \
           (is_black_turn and piece.islower()):
            interactive = True

    properties = {
        "value": PIECES[piece.lower()] if piece is not None else '',
        "interactive": interactive,
        "elem_classes": classes,
    }
    return properties


async def make_move(current_selected_piece_state):
    """
    Handles the full move cycle: get suggestions, king decides, apply move, evaluate, get jester comment.
    Yields UI updates throughout the process.
    """
    thinking_text = ""
    move_san = None
    jester_state = None
    final_board_updates = [gr.update()] * 64 # Placeholder for board updates
    final_turn_update = gr.update()
    final_eval_update = gr.update()
    final_thinking_update = gr.update()
    jester_text_update = gr.update(visible=False) # Start hidden
    jester_timer_update = gr.update(visible=False) # Start hidden

    # Reset selection visually immediately
    initial_updates = []
    selected_square_coords = None # No selection during AI move
    for r in range(8):
        for f in range(8):
            # Map Gradio grid (r=0..7 top to bottom, f=0..7 left to right)
            # to python-chess board (rank 7..0, file 0..7)
            chess_rank = 7 - r
            chess_file = f
            piece = GAME.board.piece_at_coords(chess_file, chess_rank) # Use coordinate based access
            initial_updates.append(
                gr.update(**get_cell_properties(chess_rank, chess_file, piece, selected_square=None))
            )

    # Yield initial updates (clear selection) + reset jester/thinking
    yield initial_updates + [
        gr.update(), # turn
        gr.update(value=""), # thinking
        gr.update(), # eval
        gr.update(visible=False, value=""), # jester text
        gr.update(visible=False, value=0) # jester timer
    ]


    # --- Decide Move ---
    async for kind, payload in GAME.decide_move():
        if kind == "status":
            thinking_text += f"{payload}\n"
        elif kind == "debate":
            thinking_text += f"{payload}\n" # Append debate lines directly
        elif kind == "move":
            move_san = payload
            thinking_text += f"\n**King chose move: {move_san}**\n"

        # Yield intermediate thinking updates (board doesn't change yet)
        yield final_board_updates + [final_turn_update, gr.update(value=thinking_text), final_eval_update, jester_text_update, jester_timer_update]
        await asyncio.sleep(0.05) # Small delay to allow UI to update smoothly

    if not move_san:
        thinking_text += "\n**Error: Could not decide on a move.**"
        yield final_board_updates + [final_turn_update, gr.update(value=thinking_text), final_eval_update, jester_text_update, jester_timer_update]
        return # Stop processing

    # --- Apply Move ---
    thinking_text += f"\nApplying move {move_san}..."
    yield final_board_updates + [final_turn_update, gr.update(value=thinking_text), final_eval_update, jester_text_update, jester_timer_update]

    success, message = await GAME.apply_move(move_san) # Use await for async apply_move

    if not success:
        thinking_text += f"\n**Error applying move {move_san}: {message}**"
        # Keep board as is, update thinking text
        yield final_board_updates + [final_turn_update, gr.update(value=thinking_text), final_eval_update, jester_text_update, jester_timer_update]
        return # Stop processing

    # --- Post-Move Updates (Board, Turn, Eval, Jester) ---
    thinking_text += f"\nMove {move_san} successful."

    # Get final board state
    final_board_updates = []
    for r in range(8):
        for f in range(8):
            chess_rank = 7 - r
            chess_file = f
            piece = GAME.board.piece_at_coords(chess_file, chess_rank)
            final_board_updates.append(
                gr.update(**get_cell_properties(chess_rank, chess_file, piece, selected_square=None)) # No selection
            )

    final_turn_update = gr.update(value=GAME.get_current_turn())
    final_eval_update = gr.update(value=await GAME.evaluate_board())
    final_thinking_update = gr.update(value=thinking_text) # Show final thinking log

    # Get Jester commentary
    jester_state = GAME.get_last_jester_commentary()

    if jester_state:
        jester_text = f"**{jester_state.judgement.value.upper()}!** {jester_state.joke_output}"
        jester_text_update = gr.update(value=jester_text, visible=True)
        jester_timer_update = gr.update(value=0, visible=True, label="Jester:") # Show timer bar reset

        # Yield update showing the jester message and timer bar (reset)
        yield final_board_updates + [final_turn_update, final_thinking_update, final_eval_update, jester_text_update, jester_timer_update]

        # --- Jester Timer ---
        total_time = 3.0 # seconds
        steps = 15 # Number of updates for the progress bar
        for i in range(steps + 1):
            progress = i / steps
            # Update only the progress bar while timer runs
            jester_timer_update = gr.update(value=progress, label=f"{total_time * (1-progress):.1f}s")
            # Re-yield all other final states + updated timer
            yield final_board_updates + [final_turn_update, final_thinking_update, final_eval_update, jester_text_update, jester_timer_update]
            await asyncio.sleep(total_time / steps)

        # --- Hide Jester ---
        jester_text_update = gr.update(value="", visible=False)
        jester_timer_update = gr.update(visible=False, value=0, label="Jester:") # Hide and reset
        GAME.clear_last_jester_commentary() # Clear state in backend

    # Yield final state (Jester hidden or never shown)
    yield final_board_updates + [final_turn_update, final_thinking_update, final_eval_update, jester_text_update, jester_timer_update]


def choose_piece(row: int, col: int, current_selected_piece_state: dict | None):
    """ Handles user clicking on a piece to select it for prompting. """
    # Map Gradio grid (row 0-7 top-down, col 0-7 left-right)
    # to python-chess coordinates (rank 7-0, file 0-7)
    chess_rank = 7 - row
    chess_file = col
    selected_square = (chess_rank, chess_file)

    piece_symbol = GAME.board.piece_at_coords(chess_file, chess_rank) # Get piece char ('P', 'n', etc.)

    if piece_symbol is None: # Clicked empty square
         log_warning("Clicked empty square, cannot select for prompt.")
         # Just return updates to redraw board without selection
         updates = []
         for r in range(8):
             for f in range(8):
                 cr = 7 - r
                 cf = f
                 p = GAME.board.piece_at_coords(cf, cr)
                 updates.append(
                     gr.update(**get_cell_properties(cr, cf, p, selected_square=None))
                 )
         # Return state unchanged, update board only
         return [current_selected_piece_state, gr.update(), gr.update()] + updates


    piece_name_key = piece_symbol.lower()
    if piece_name_key not in SHORT_PIECE_MAP:
        log_error(f"Invalid piece symbol '{piece_symbol}' at {chess_file},{chess_rank}")
        return [current_selected_piece_state, gr.update(), gr.update()] # Should not happen

    piece_name = SHORT_PIECE_MAP[piece_name_key] # 'pawn', 'knight', etc.
    turn = GAME.get_current_turn() # 'white' or 'black'

    # Check if the piece belongs to the current player
    is_white_turn = turn == 'white'
    can_select = (is_white_turn and piece_symbol.isupper()) or \
                 (not is_white_turn and piece_symbol.islower())

    if not can_select:
        log_warning(f"Cannot select opponent's piece ({piece_symbol}) on {turn}'s turn.")
        # Redraw board without selection
        updates = []
        for r in range(8):
             for f in range(8):
                 cr = 7 - r
                 cf = f
                 p = GAME.board.piece_at_coords(cf, cr)
                 updates.append(
                     gr.update(**get_cell_properties(cr, cf, p, selected_square=None))
                 )
         return [current_selected_piece_state, gr.update(), gr.update()] + updates


    log_info(f"Selected piece: {piece_name} ({piece_symbol}) at r{row},c{col} (chess {chess_file},{chess_rank}) for {turn}")

    prompt_text = GAME.get_fraction_user_prompt(turn, piece_name) or "" # Get existing prompt or empty string

    # Store selection state (piece name, color, square)
    new_selected_piece_state = {
        "name": piece_name,
        "color": turn,
        "square": selected_square # Store chess coords (rank, file)
    }

    # Update board highlighting the selected piece
    board_updates = []
    for r in range(8):
        for f in range(8):
            # Map Gradio grid to chess coords
            cr = 7 - r
            cf = f
            p = GAME.board.piece_at_coords(cf, cr)
            board_updates.append(
                gr.update(**get_cell_properties(cr, cf, p, selected_square=selected_square))
            )

    # Return new state, prompt image, prompt text, and board updates
    return [
        new_selected_piece_state, # Update the state
        gr.update(
            value=PIECES[piece_name_key], # Show selected piece symbol
            # Use CSS classes for color based on whose turn it is
            elem_classes=["figure-img", f"cell-{turn}-fg"]
        ),
        gr.update(value=prompt_text), # Show current prompt
    ] + board_updates


def save_prompt(new_prompt: str, selected_piece_state: dict | None):
    """ Saves the updated prompt text for the currently selected piece fraction. """
    if not selected_piece_state:
        log_warning("Save prompt called but no piece selected.")
        return gr.update() # No change feedback needed? Or maybe a status message?

    color = selected_piece_state.get("color")
    piece_name = selected_piece_state.get("name")

    if not color or not piece_name:
         log_error(f"Invalid selected piece state for saving prompt: {selected_piece_state}")
         return gr.update() # Error feedback?

    log_info(f"Saving prompt for {color} {piece_name}: '{new_prompt}'")
    success = GAME.update_fraction_prompt(color, piece_name, new_prompt)

    if not success:
         log_warning(f"Failed to save prompt for {color} {piece_name}.")
         # Optionally provide feedback to the user via a status component
         # return gr.update(value="Failed to save prompt!")

    # No explicit UI update needed just for saving, maybe a confirmation?
    # For now, return no update
    return gr.update()


def make_board_layout(selected_piece_state, prompt_img, prompt_text):
    """ Creates the Gradio layout for the chessboard and labels. """
    board_buttons = [] # Store button objects
    with gr.Column(scale=0): # Container for the board and labels
        # Top Row: Evaluation Slider
        with gr.Row():
             thermo = gr.Slider(
                 minimum=-10, maximum=10, step=0.1,
                 value=0,
                 interactive=False,
                 label="Evaluation",
                 elem_classes=["thermo"]
             )
        # Middle Row: Rank Labels + Board + File Labels
        with gr.Row(equal_height=False):
            # Rank labels (8 to 1) - Left Column
            with gr.Column(min_width=30, scale=0): # Narrow column for ranks
                 for r in range(8, 0, -1):
                     gr.Markdown(f"{r}", elem_classes=["rank-file-label"])

            # Chessboard Grid (8x8) - Middle Columns
            with gr.Column(scale=8): # Main board area
                for r in range(8): # Gradio rows (0-7, top to bottom)
                    with gr.Row(equal_height=True):
                         for f in range(8): # Gradio columns (0-7, left to right)
                             # Map to chess coords
                             chess_rank = 7 - r
                             chess_file = f
                             piece = GAME.board.piece_at_coords(chess_file, chess_rank)
                             button = gr.Button(**get_cell_properties(chess_rank, chess_file, piece, selected_square=None))
                             # Add click handler
                             button.click(
                                 fn=partial(choose_piece, r, f), # Pass Gradio row/col
                                 inputs=[selected_piece_state],
                                 outputs=[selected_piece_state, prompt_img, prompt_text] + board_buttons, # Update state, prompt, board
                                 queue=False, # Fast interaction for selection
                             )
                             board_buttons.append(button) # Add to list *after* creating handler

            # File labels (a to h) - Bottom Row (within the board container column)
            with gr.Row(equal_height=False):
                 gr.Markdown("", elem_classes=["rank-file-label"]) # Spacer for rank column
                 for f_char_code in range(ord('a'), ord('h') + 1):
                     gr.Markdown(f"{chr(f_char_code)}", elem_classes=["rank-file-label"])

    return board_buttons, thermo # Return button list and slider


def main():
    """ Main function to set up and launch the Gradio interface. """
    with gr.Blocks(css=CSS, title="Prompt Chess") as demo:
        # --- State Management ---
        # Store selected piece info {name, color, square:(rank,file)}
        selected_piece_state = gr.State(None)

        gr.Markdown("# Prompt Chess")

        with gr.Row():
            # --- Left Column: Controls & Info ---
            with gr.Column(scale=1, min_width=300):
                with gr.Row(): # Piece selection display
                    with gr.Column(scale=0, min_width=70):
                        prompt_img = gr.Textbox(
                            label="Fraction", interactive=False,
                            elem_classes=["figure-img", "cell"], # Use cell class for size
                            max_lines=1
                        )
                    with gr.Column(scale=1): # Info next to piece image
                        turn = gr.Textbox(label="Turn", value=GAME.get_current_turn(), interactive=False)
                        # Add prompt input
                        prompt_text = gr.Textbox(label="Instructions", interactive=True, lines=3)
                        # Add save button for prompt
                        save_button = gr.Button("Save Instructions")

                # Add Make Move button below instructions
                with gr.Row():
                     move_button = gr.Button("Make AI Move")

                # Add Thinking/Log Area
                with gr.Row():
                     thinking = gr.Markdown(value="", label="Thinking Log") # Use Markdown for formatting

                # *** ADDED: Jester Output Area ***
                with gr.Row():
                     with gr.Column(elem_classes=["jester-box"]): # Wrap in styled box
                         jester_output = gr.Markdown(label="Jester's Quip", value="", visible=False)
                         jester_timer = gr.Progress(label="Jester:", visible=False, value=0) # Timer bar

            # --- Right Column: Chessboard ---
            with gr.Column(scale=0, min_width=620): # Fixed min width based on cell size + labels
                 board_buttons, thermo = make_board_layout(selected_piece_state, prompt_img, prompt_text)

        # --- Event Handlers ---
        # Save button click
        save_button.click(
            fn=save_prompt,
            inputs=[prompt_text, selected_piece_state],
            outputs=None, # Or a status message component
            queue=False, # Quick action
        )

        # Make Move button click
        move_button.click(
            fn=make_move,
            inputs=[selected_piece_state], # Pass current selection state (though AI doesn't use it)
            # Outputs: board buttons, turn indicator, thinking log, eval slider, jester text, jester timer
            outputs=board_buttons + [turn, thinking, thermo, jester_output, jester_timer],
            queue=True, # Long-running task
        )

    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()