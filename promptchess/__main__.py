import asyncio
import random
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

/* —— Health-bar colours —— */
.health-white .gr-slider__bar { background:#dddddd; }
.health-black .gr-slider__bar { background:#222222; }
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
        # ───────── live-streamed “thinking” lines ──────────
        if kind in ("debate", "status"):
            thinking_text += payload + "\n"
            dummy_updates = [gr.update()] * 64
            yield dummy_updates + [
                gr.update(),                          # turn
                gr.update(value=thinking_text),       # thinking
                gr.update(),                          # white health
                gr.update(),                          # black health
                gr.update(),                          # white points
                gr.update(),                          # black points
                gr.update(),                          # jester slot
            ]

        # ───────── King finally chose a move ──────────
        elif kind == "move":
            move = payload
            # ------------------------- CHANGED -----------------------
            success, msg = GAME.apply_move(move)      # call GameState logic
            if not success:
                raise ValueError(msg)
            # --------------------------------------------------------

            # refreshed stats AFTER apply_move
            white_hp, black_hp   = GAME.get_health_scores()
            white_pts, black_pts = GAME.get_points()
            jester               = await GAME.get_jester_comment()

            popup_body = (
                f"<div>"
                f"🃏 <b>{jester.joke_output}</b><br/>"
                f"<i>{jester.judgement.value.title()}</i>"
                f"</div>"
            )
            # random position (10–80 vh, 5–70 vw)
            top_vh, left_vw = random.randint(10, 80), random.randint(5, 70)
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

            outputs = board_updates + [
                GAME.board.get_turn(),                 # turn
                gr.update(value=thinking_text),        # thinking
                gr.update(value=white_hp),             # white health
                gr.update(value=black_hp),             # black health
                gr.update(value=white_pts),            # white points
                gr.update(value=black_pts),            # black points
                gr.update(value=popup_html, visible=True),
            ]
            yield outputs

            # keep it visible 5 s
            await asyncio.sleep(5)
            yield (
                [gr.update()] * (64 + 6)               # board + turn + thinking + 2 health + 2 points
                + [gr.update(visible=False)]           # hide jester
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
        # ───── health sliders row ─────────────────────────
        with gr.Row():
            health_white = gr.Slider(
                minimum=0, maximum=49, step=1, value=49,
                interactive=False, label="White health",
                elem_classes=["thermo", "health-white"],
            )
            health_black = gr.Slider(
                minimum=0, maximum=49, step=1, value=49,
                interactive=False, label="Black health",
                elem_classes=["thermo", "health-black"],
            )

        # ───── NEW points sliders row ─────────────────────
        with gr.Row():
            points_white = gr.Slider(
                minimum=0, maximum=200, step=1, value=0,
                interactive=False, label="White points",
                elem_classes=["thermo", "health-white"],
            )
            points_black = gr.Slider(
                minimum=0, maximum=200, step=1, value=0,
                interactive=False, label="Black points",
                elem_classes=["thermo", "health-black"],
            )

        # ───── chessboard grid ────────────────────────────
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

    # attach click handler to every square
    for idx, btn in enumerate(buttons):
        r, c = divmod(idx, 8)
        btn.click(
            fn=partial(choose_piece, r, c),
            outputs=[prompt_img, prompt, selected_piece] + buttons,
            queue=False,
        )

    # return widgets for later updates
    return buttons, health_white, health_black, points_white, points_black


def main():
    with gr.Blocks(css=CSS) as demo:
        selected_piece = gr.State(None)
        gr.Markdown("### Prompt Chess")
        with gr.Row():
            # ─── left control panel ───────────────────────
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
                    thinking = gr.Markdown(label="Thinking…")
                with gr.Row():
                    jester_box = gr.Markdown("", visible=False)

            # ─── right chessboard panel ───────────────────
            with gr.Column(min_width=760, scale=0):
                with gr.Row():
                    chess_board, health_white, health_black, points_white, points_black = make_board(
                        selected_piece, prompt_img, prompt
                    )

            # ─── click handler for “Make move” ───────────
            move.click(
                fn=make_move,
                outputs=chess_board + [
                    turn,
                    thinking,
                    health_white, health_black,
                    points_white, points_black,
                    jester_box,
                ],
                queue=True,
            )

    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
