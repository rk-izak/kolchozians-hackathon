import gradio as gr
from functools import partial

from .chessboard import ChessBoard
from .game_state import GameState
from .visualize import visualize

CSS = """
.cell-button {
    width: 70px !important;
    height: 70px !important;
    font-size: 48px !important;
    padding: 0 !important;
}
.figure-img textarea {
    font-size: 128px !important;
    text-align: center;
}
"""

def random_move(board):
    moves = board.get_legal_moves()
    board.apply_move(moves[0])

    updates = []
    for r in range(8):
        for c in range(7, -1, -1):
            piece = board.piece_at(c, r)
            
            check_active = False
            if piece is not None:
                if board.get_turn() == 'white':
                    check_active = piece.isupper()
                else:
                    check_active = piece.islower()
            
            updates.append(
                gr.update(
                    value=visualize(piece),
                    interactive=check_active
                )
            )
    updates.append(board.get_turn())
    return updates

def change_prompt(row, col, game):
    return [visualize(game.board.piece_at(7-col, row)), "PROMPT"]

def make_board(game, prompt_img, prompt):
    buttons = []
    with gr.Row() as chess_board:
        for col in range(8):
            with gr.Column(min_width=70, scale=0): 
                for row in range(7, -1, -1):
                    piece = game.board.piece_at(row, col)
                    b = gr.Button(
                        value=visualize(piece),
                        interactive=piece is not None and piece.isupper(),
                        elem_classes=["cell-button"]
                    )
                    buttons.append(b)

    for idx, btn in enumerate(buttons):
        r, c = divmod(idx, 8)
        btn.click(
            fn=partial(change_prompt, r, c),
            inputs=gr.State(game),
            outputs=[prompt_img, prompt],
            queue=False,
        )
    return buttons


def main():
    game = GameState()

    with gr.Blocks(css=CSS) as demo:
        gr.Markdown("### Prompt Chess")
        with gr.Row():
            with gr.Column(scale=0):
                turn = gr.Textbox(label="Turn", value=game.board.get_turn(), interactive=False)
            with gr.Column(scale=1):
                clicked = gr.Textbox(label="Prompt", interactive=False)
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        prompt_img = gr.Textbox(label="Figure", interactive=False, elem_classes=["figure-img"])
                    with gr.Column(scale=1):
                        prompt = gr.Textbox(label="Thinking...", interactive=True)
                    with gr.Column(scale=0):
                        move = gr.Button(value="Make move")
            with gr.Column(min_width=760, scale=0):
                chess_board = make_board(game, prompt_img, prompt)
                move.click(
                    fn=random_move,
                    inputs=gr.State(game.board),
                    outputs=chess_board + [turn],
                    queue=False,
                )
    demo.launch()


if __name__ == "__main__":
    main()
