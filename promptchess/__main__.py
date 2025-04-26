import gradio as gr
from functools import partial

from .game_state import GameState, SHORT_PIECE_MAP


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
}
.cell-white-fg {
    color: #DDDDDD;
}
.cell-white-bg {
    background-color: #BBBBA0;
}
.cell-black-fg {
    color: #111111;
}
.cell-black-bg {
    background-color: #769455;
}

.figure-img textarea {
    font-size: 128px !important;
    text-align: center;
}
"""


GAME = GameState()


def get_cell_properties(rank: int, file: int, piece: str | None) -> dict:
    classes = ["cell", ["cell-black-bg", "cell-white-bg"][(file + rank) % 2]]
    if piece is not None:
        classes.append("cell-black-fg" if piece.islower() else "cell-white-fg")

    interactive = (
        piece is not None
        and (
            GAME.board.get_turn() == "white" and piece.isupper()
            or GAME.board.get_turn() == "black" and piece.islower()
        )
    )

    properties = {
        "value": PIECES[piece.lower()] if piece is not None else '',
        "interactive": interactive,
        "elem_classes": classes,
    }
    return properties


async def random_move():
    move = await GAME.decide_move()
    GAME.board.apply_move(move)

    updates = []
    for rank in range(8):
        for file in range(7, -1, -1):
            piece = GAME.board.piece_at(file, rank)
            updates.append(gr.update(**get_cell_properties(rank, file, piece)))
    updates.append(GAME.board.get_turn())
    return updates


def choose_piece(row, col):
    piece = GAME.board.piece_at(7-col, row)
    assert piece is not None
    piece_name = SHORT_PIECE_MAP[piece.lower()]
    turn = GAME.board.get_turn()
    prompt = GAME.get_fraction_user_prompt(turn, piece_name)
    return [PIECES[piece], prompt, piece_name]


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
        for file in range(8):
            with gr.Column(min_width=70, scale=0): 
                for rank in range(7, -1, -1):
                    piece = GAME.board.piece_at(rank, file)
                    buttons.append(gr.Button(**get_cell_properties(rank, file, piece)))

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
