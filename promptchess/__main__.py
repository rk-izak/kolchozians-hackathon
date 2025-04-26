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
.cell-white-fg textarea{
    color: #DDDDDD;
}
.cell-white-bg {
    background-color: #BBBBA0;
}
.cell-black-fg{
    color: #111111;
}
.cell-black-fg textarea{
    color: #111111;
}
.cell-black-bg {
    background-color: #769455;
}
.cell-border {
    border: 5px solid red;
}

.figure-img textarea {
    font-size: 128px !important;
    text-align: center;
}

button.cell:disabled,
.gr-button:disabled.cell {
    opacity: 0.7   !important;
    cursor : default !important;
}

.rank-file-label {
    width:      70px;
    height:     70px;
    font-size:  40px;
}
"""


GAME = GameState()

def get_cell_properties(rank: int, file: int, piece: str | None, selected_piece: str | None = None) -> dict:
    classes = ["cell", ["cell-black-bg", "cell-white-bg"][(file + rank) % 2]]
    if piece is not None:
        classes.append("cell-black-fg" if piece.islower() else "cell-white-fg")
        if selected_piece is not None and piece == selected_piece:
            classes.append("cell-border")

    interactive = (
        piece is not None
        and (
            GAME.board.get_turn() == "white" and piece.isupper()
            or GAME.board.get_turn() == "black" and piece.islower()
        )
        and piece.lower() != "k"
    )

    properties = {
        "value": PIECES[piece.lower()] if piece is not None else '',
        "interactive": interactive,
        "elem_classes": classes,
    }
    return properties


async def make_move():
    thinking_text = ""
    async for kind, payload in GAME.decide_move():
        if kind in ("debate", "status"):
            thinking_text += payload + "\n"
            dummy_board_updates = [gr.update()]*64
            dummy_turn = gr.update()
            yield dummy_board_updates + [dummy_turn, gr.update(value=thinking_text)]

        elif kind == "move":
            move = payload
            GAME.board.apply_move(move)
            updates = []
            for r in range(8):
                for c in range(7, -1, -1):
                    piece = GAME.board.piece_at(c, r)    
                    updates.append(
                        gr.update(**get_cell_properties(r, c, piece))
                    )
            updates += [GAME.board.get_turn(), gr.update(value=thinking_text)]
            yield  updates


def choose_piece(row, col):
    piece = GAME.board.piece_at(7-col, row)
    assert piece is not None
    piece_name = SHORT_PIECE_MAP[piece.lower()]
    turn = GAME.board.get_turn()
    prompt = GAME.get_fraction_user_prompt(turn, piece_name)

    updates = []
    for r in range(8):
        for c in range(7, -1, -1):
            updates.append(
                gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r), piece))
            )

    return [
        gr.update(
            value=PIECES[piece.lower()],
            elem_classes=["figure-img", f"cell-{turn}-fg"]
        ),
        prompt,
        piece_name
    ] + updates


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
        with gr.Column(min_width=24, scale=0):          # narrow column
            for rank in range(8, 0, -1):
                gr.Markdown(f"# {rank}", elem_classes=["rank-file-label"])
        for file in range(8):
            with gr.Column(min_width=70, scale=0): 
                for rank in range(7, -1, -1):
                    piece = GAME.board.piece_at(rank, file)
                    buttons.append(gr.Button(**get_cell_properties(rank, file, piece)))

    with gr.Row():
        gr.Markdown(" ")
        for file in range(8):
            letter = chr(ord('a') + file)
            gr.Markdown(f"# {letter}", elem_classes=["rank-file-label"])
    
    for idx, btn in enumerate(buttons):
        r, c = divmod(idx, 8)
        btn.click(
            fn=partial(choose_piece, r, c),
            outputs=[prompt_img, prompt, selected_piece] + buttons,
            queue=False,
        )
    return buttons


def main():

    with gr.Blocks(css=CSS) as demo:
        selected_piece = gr.State(None)
        gr.Markdown("### Prompt Chess")
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        prompt_img = gr.Textbox(label="Fraction", interactive=False, elem_classes=["figure-img"])
                    with gr.Column(scale=1):
                        with gr.Row():
                            turn = gr.Textbox(label="Turn", value=GAME.board.get_turn(), interactive=False)
                        with gr.Row():
                            prompt = gr.Textbox(label="Instructions", interactive=True)
                            prompt.change(
                                fn=save_prompt,
                                inputs=[prompt, selected_piece],
                                outputs=None,
                                queue=False,
                            )
                        with gr.Row():
                            move = gr.Button(value="Make move")
                with gr.Row():
                    thinking = gr.Markdown(label="Thinking...")

            with gr.Column(min_width=760, scale=0):
                chess_board = make_board(selected_piece, prompt_img, prompt)
                move.click(
                    fn=make_move,
                    outputs=chess_board + [turn, thinking],
                    queue=True,
                )
    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
