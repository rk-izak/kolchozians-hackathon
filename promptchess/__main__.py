import gradio as gr
from functools import partial

from .game_state import GameState, SHORT_PIECE_MAP
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

GAME = GameState()

async def random_move():
    move = await GAME.decide_move()
    GAME.board.apply_move(move)

    updates = []
    for r in range(8):
        for c in range(7, -1, -1):
            piece = GAME.board.piece_at(c, r)
            
            check_active = False
            if piece is not None:
                if GAME.board.get_turn() == 'white':
                    check_active = piece.isupper()
                else:
                    check_active = piece.islower()
            
            updates.append(
                gr.update(
                    value=visualize(piece),
                    interactive=check_active
                )
            )
    updates.append(GAME.board.get_turn())
    return updates

def choose_piece(row, col):
    piece_name = SHORT_PIECE_MAP[GAME.board.piece_at(7-col, row).lower()]
    turn = GAME.board.get_turn()
    prompt = GAME.get_fraction_user_prompt(turn, piece_name)
    return [visualize(GAME.board.piece_at(7-col, row)), prompt, piece_name]

def save_prompt(
    new_prompt: str,
    selected: str | None,
):
    if selected is None:
        return

    turn = GAME.board.get_turn()
    GAME.update_fraction_prompt(turn, selected, new_prompt)

def make_board(selected_piece, prompt_img, prompt):
    buttons = []
    with gr.Row() as chess_board:
        for col in range(8):
            with gr.Column(min_width=70, scale=0): 
                for row in range(7, -1, -1):
                    piece = GAME.board.piece_at(row, col)
                    b = gr.Button(
                        value=visualize(piece),
                        interactive=piece is not None and piece.isupper(),
                        elem_classes=["cell-button"]
                    )
                    buttons.append(b)

    for idx, btn in enumerate(buttons):
        r, c = divmod(idx, 8)
        btn.click(
            fn=partial(choose_piece, r, c),
            outputs=[prompt_img, prompt, selected_piece],
            queue=False,
        )
    return buttons


def main():

    with gr.Blocks(css=CSS) as demo:
        selected_piece = gr.State(None)
        gr.Markdown("### Prompt Chess")
        with gr.Row():
            with gr.Column(scale=0):
                turn = gr.Textbox(label="Turn", value=GAME.board.get_turn(), interactive=False)
            with gr.Column(scale=1):
                clicked = gr.Textbox(label="Prompt", interactive=False)
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        prompt_img = gr.Textbox(label="Figure", interactive=False, elem_classes=["figure-img"])
                    with gr.Column(scale=1):
                        prompt = gr.Textbox(label="Thinking...", interactive=True)
                        prompt.change(
                            fn=save_prompt,
                            inputs=[prompt, selected_piece],
                            outputs=None,
                            queue=False,
                        )
                    with gr.Column(scale=0):
                        move = gr.Button(value="Make move")
            with gr.Column(min_width=760, scale=0):
                chess_board = make_board(selected_piece, prompt_img, prompt)
                move.click(
                    fn=random_move,
                    outputs=chess_board + [turn],
                    queue=False,
                )
    demo.launch()


if __name__ == "__main__":
    main()
