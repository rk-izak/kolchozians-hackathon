import asyncio
import random                                           # ← NEW
import gradio as gr
from functools import partial

from .game_state import GameState, SHORT_PIECE_MAP


PIECES = {
    "p": "♟", "r": "♜", "b": "♝",
    "q": "♛", "k": "♚", "n": "♞",
}

CSS = """
.cell {
    width: 70px !important;
    height: 70px !important;
    font-size: 48px !important;
    padding: 0 !important;
}
.cell-white-fg            { color: #DDDDDD; }
.cell-white-fg textarea   { color: #DDDDDD; }
.cell-white-bg            { background-color: #BBBBA0; }
.cell-black-fg            { color: #111111; }
.cell-black-fg textarea   { color: #111111; }
.cell-black-bg            { background-color: #769455; }
.cell-border              { border: 5px solid red; }

.figure-img textarea      { font-size: 128px !important; text-align: center; }

button.cell:disabled,
.gr-button:disabled.cell { opacity: 0.7 !important; cursor: default !important; }

.rank-file-label {
    width: 70px; height: 70px; font-size: 40px;
}

.thermo { width: 100%; }

/* —— Jester pop-up —— */
.jester-popup {
  position: fixed;
  background: linear-gradient(135deg,#ff65e6 0%,#ffd86b 50%,#65ffda 100%);
  border: 4px dashed #4b0082;
  border-radius: 20px;
  padding: 20px 24px;
  font-size: 22px;
  font-weight: 600;
  color: #000;
  max-width: 320px;
  box-shadow: 0 6px 14px rgba(0,0,0,.45);
  z-index: 1000;
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

    return {
        "value": PIECES[piece.lower()] if piece is not None else "",
        "interactive": interactive,
        "elem_classes": classes,
    }


async def make_move():
    thinking_text = ""
    async for kind, payload in GAME.decide_move():
        if kind in ("debate", "status"):
            thinking_text += payload + "\n"
            dummy_updates = [gr.update()] * 64
            yield dummy_updates + [
                gr.update(),                          # turn
                gr.update(value=thinking_text),       # thinking
                gr.update(),                          # eval slider
                gr.update(),                          # jester slot
            ]

        elif kind == "move":
            move = payload
            GAME.board.apply_move(move)

            evaluation = await GAME.evaluate_board()
            jester     = await GAME.get_jester_comment()

            popup_body = (
                f"<div>"
                f"🃏 <b>{jester.joke_output}</b><br/>"
                f"<i>{jester.judgement.value.title()}</i>"
                f"</div>"
            )

            # random position (10–80 vh, 5–70 vw)
            top_vh  = random.randint(10, 80)
            left_vw = random.randint(5, 70)
            popup_html = (
                f'<div class="jester-popup" '
                f'style="top:{top_vh}vh; left:{left_vw}vw;">'
                f"{popup_body}</div>"
            )

            board_updates = []
            for r in range(8):
                for c in range(7, -1, -1):
                    board_updates.append(
                        gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r)))
                    )

            outputs = (
                board_updates
                + [
                    GAME.board.get_turn(),             # turn
                    gr.update(value=thinking_text),    # thinking
                    evaluation,                        # slider
                    gr.update(value=popup_html, visible=True),
                ]
            )
            yield outputs

            # keep it visible 5 s
            await asyncio.sleep(5)
            yield (
                [gr.update()] * (64 + 3)               # board + turn + thinking + slider unchanged
                + [gr.update(visible=False)]
            )


def choose_piece(row, col):
    piece = GAME.board.piece_at(7 - col, row)
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
            elem_classes=["figure-img", f"cell-{turn}-fg"],
        ),
        prompt,
        piece_name,
    ] + updates


def save_prompt(new_prompt: str, selected: str | None):
    if selected is None:
        return
    GAME.update_fraction_prompt(GAME.board.get_turn(), selected, new_prompt)


def make_board(selected_piece, prompt_img, prompt):
    buttons = []
    with gr.Column():
        with gr.Row():
            thermo = gr.Slider(
                minimum=-10,
                maximum=10,
                step=0.1,
                value=0,
                interactive=False,
                label="evaluation",
                elem_classes=["thermo"],
            )
        with gr.Row() as chess_board:
            with gr.Column(min_width=24, scale=0):
                for rank in range(8, 0, -1):
                    gr.Markdown(f"# {rank}", elem_classes=["rank-file-label"])
            for file in range(8):
                with gr.Column(min_width=70, scale=0):
                    for rank in range(7, -1, -1):
                        buttons.append(
                            gr.Button(**get_cell_properties(rank, file, GAME.board.piece_at(rank, file)))
                        )

        with gr.Row():
            gr.Markdown(" ")
            for file in range(8):
                letter = chr(ord("a") + file)
                gr.Markdown(f"# {letter}", elem_classes=["rank-file-label"])
    for idx, btn in enumerate(buttons):
        r, c = divmod(idx, 8)
        btn.click(
            fn=partial(choose_piece, r, c),
            outputs=[prompt_img, prompt, selected_piece] + buttons,
            queue=False,
        )
    return buttons, thermo


def main():
    with gr.Blocks(css=CSS) as demo:
        selected_piece = gr.State(None)
        gr.Markdown("### Prompt Chess")
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        prompt_img = gr.Textbox(
                            label="Fraction", interactive=False, elem_classes=["figure-img"]
                        )
                    with gr.Column(scale=1):
                        with gr.Row():
                            turn = gr.Textbox(
                                label="Turn",
                                value=GAME.board.get_turn(),
                                interactive=False,
                            )
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
                with gr.Row():
                    jester_box = gr.Markdown(
                        "", visible=False  # visibility toggled by make_move
                    )

            with gr.Column(min_width=760, scale=0):
                with gr.Row():
                    chess_board, thermo = make_board(selected_piece, prompt_img, prompt)

            move.click(
                fn=make_move,
                outputs=chess_board + [turn, thinking, thermo, jester_box],
                queue=True,
            )

    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
