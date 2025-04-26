import asyncio
import logging
import random
from enum import Enum
from functools import partial

import gradio as gr

from .game_agents.prompt_agent import PromptAgent
from .game_state import EFFICIENT_MODEL, SHORT_PIECE_MAP, GameState


class GameMode(Enum):
    HUMAN_VS_HUMAN = 'Human vs Human'
    HUMAN_VS_AGENT = 'Human vs Agent'
    AGENT_VS_AGENT = 'Agent vs Agent'


PIECES = {
    'p': '♟',
    'r': '♜',
    'b': '♝',
    'q': '♛',
    'k': '♚',
    'n': '♞',
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

/* —— Game mode selection —— */
.mode-selector { margin-bottom: 20px; }
"""

GAME = None
WHITE_AGENT = None
BLACK_AGENT = None
CURRENT_GAME_MODE = GameMode.HUMAN_VS_HUMAN


def initialize_game(game_mode):
    global GAME, WHITE_AGENT, BLACK_AGENT, CURRENT_GAME_MODE

    CURRENT_GAME_MODE = GameMode(game_mode)

    # Initialize agents based on selected mode
    if CURRENT_GAME_MODE == GameMode.HUMAN_VS_AGENT:
        # Create AI agent for black
        BLACK_AGENT = PromptAgent(color='black', model=EFFICIENT_MODEL)
        WHITE_AGENT = None
    elif CURRENT_GAME_MODE == GameMode.AGENT_VS_AGENT:
        # Create AI agents for both sides
        WHITE_AGENT = PromptAgent(color='white', model=EFFICIENT_MODEL)
        BLACK_AGENT = PromptAgent(color='black', model=EFFICIENT_MODEL)
    else:
        # Human vs Human - no agents needed
        WHITE_AGENT = None
        BLACK_AGENT = None

    # Initialize the game
    GAME = GameState()

    # Create board updates with the initial positions
    board_updates = []
    for r in range(8):
        for c in range(7, -1, -1):
            board_updates.append(gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r))))

    # Return updates for UI including board pieces
    return board_updates + [
        gr.update(value=GAME.board.get_turn()),  # turn
        gr.update(value='Game initialized with mode: ' + game_mode),  # thinking
        gr.update(value=49),  # white health
        gr.update(value=49),  # black health
        gr.update(visible=False),  # jester box
    ]


def get_cell_properties(
    rank: int, file: int, piece: str | None, selected_piece: str | None = None
) -> dict:
    classes = ['cell', ['cell-black-bg', 'cell-white-bg'][(file + rank) % 2]]
    if piece is not None:
        classes.append('cell-black-fg' if piece.islower() else 'cell-white-fg')
        if selected_piece is not None and piece == selected_piece:
            classes.append('cell-border')

    # Determine if the piece should be interactive
    if piece is None:
        interactive = False
    elif piece.lower() == 'k':
        interactive = False
    else:
        current_turn = GAME.board.get_turn()
        is_user_turn = True

        # Check if it's an agent's turn
        if current_turn == 'white' and WHITE_AGENT is not None:
            is_user_turn = False
        elif current_turn == 'black' and BLACK_AGENT is not None:
            is_user_turn = False

        # Piece is interactive if it's user's turn and piece color matches turn
        interactive = is_user_turn and (
            current_turn == 'white'
            and piece.isupper()
            or current_turn == 'black'
            and piece.islower()
        )

    return {
        'value': PIECES[piece.lower()] if piece is not None else '',
        'interactive': interactive,
        'elem_classes': classes,
    }


# Helper function to clear the fraction and prompt displays
def clear_prompt_displays():
    return [
        gr.update(value=''),  # prompt_img
        gr.update(value=''),  # prompt
    ]


async def agent_move(prompt_updates=None):
    """Handle agent move if it's an agent's turn"""
    current_turn = GAME.board.get_turn()
    agent = WHITE_AGENT if current_turn == 'white' else BLACK_AGENT

    thinking_text = ''

    # First, update a prompt if needed
    if prompt_updates is None and CURRENT_GAME_MODE != GameMode.HUMAN_VS_HUMAN:
        thinking_text += f'Agent ({current_turn}) is deciding on a prompt update...\n'
        # Clear prompt displays immediately
        prompt_clears = clear_prompt_displays()
        dummy_updates = [gr.update()] * 64
        yield (
            dummy_updates
            + [
                gr.update(),  # turn
                gr.update(value=thinking_text),  # thinking
                gr.update(),  # white health
                gr.update(),  # black health
                gr.update(),  # jester slot
            ]
            + prompt_clears
        )

        # Get current prompts for the agent
        current_prompts = {}
        for piece_type in ['pawn', 'knight', 'bishop', 'rook', 'queen']:
            prompt = GAME.get_fraction_user_prompt(current_turn, piece_type)
            if prompt:
                current_prompts[piece_type] = prompt

        try:
            prompt_updates = await agent.decide_single_prompt_update(GAME.board, current_prompts)
            if prompt_updates:
                thinking_text += f'Agent ({current_turn}) updated {prompt_updates.piece_type} prompt: {prompt_updates.new_prompt}\n'
                thinking_text += f'Reasoning: {prompt_updates.reasoning}\n\n'
        except Exception as e:
            thinking_text += f'Error getting prompt update: {e}\n\n'

    # If we received prompt updates from the agent, apply them
    if prompt_updates:
        piece_type = prompt_updates.piece_type
        new_prompt = prompt_updates.new_prompt
        GAME.update_fraction_prompt(current_turn, piece_type, new_prompt)
        if 'updated' not in thinking_text:
            thinking_text += f'Agent ({current_turn}) updated {piece_type} prompt: {new_prompt}\n\n'

    thinking_text += f'Agent ({current_turn}) is deciding on a move...\n'
    # Get the agent to decide the move
    async for kind, payload in GAME.decide_move():
        # Live-streamed "thinking" lines
        if kind in ('debate', 'status'):
            thinking_text += payload + '\n'
            dummy_updates = [gr.update()] * 64
            yield (
                dummy_updates
                + [
                    gr.update(),  # turn
                    gr.update(value=thinking_text),  # thinking
                    gr.update(),  # white health
                    gr.update(),  # black health
                    gr.update(),  # jester slot
                ]
                + clear_prompt_displays()
            )

        # King chose a move
        elif kind == 'move':
            move = payload
            GAME.board.apply_move(move)

            white_hp, black_hp = GAME.get_health_scores()
            jester = await GAME.get_jester_comment()

            popup_body = (
                f'<div>'
                f'🃏 <b>{jester.joke_output}</b><br/>'
                f'<i>{jester.judgement.value.title()}</i>'
                f'</div>'
            )
            # Random position (10–80 vh, 5–70 vw)
            top_vh, left_vw = random.randint(10, 80), random.randint(5, 70)
            popup_html = (
                f'<div class="jester-popup" '
                f'style="top:{top_vh}vh; left:{left_vw}vw;">'
                f'{popup_body}</div>'
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
                    GAME.board.get_turn(),  # turn
                    gr.update(value=thinking_text),  # thinking
                    gr.update(value=white_hp),  # white health
                    gr.update(value=black_hp),  # black health
                    gr.update(value=popup_html, visible=True),
                ]
                + clear_prompt_displays()
            )
            yield outputs

            # Keep jester visible for 5s
            await asyncio.sleep(5)
            yield (
                [gr.update()] * (64 + 4)  # board + turn + thinking + 2 bars
                + [gr.update(visible=False)]  # hide jester
                + clear_prompt_displays()
            )

            # Check if the next turn is also an agent's turn
            next_turn = GAME.board.get_turn()
            if (next_turn == 'white' and WHITE_AGENT is not None) or (
                next_turn == 'black' and BLACK_AGENT is not None
            ):
                # If it's agent vs agent, add a small delay between moves
                if CURRENT_GAME_MODE == GameMode.AGENT_VS_AGENT:
                    await asyncio.sleep(2)

                # Trigger the next agent move
                next_agent = WHITE_AGENT if next_turn == 'white' else BLACK_AGENT
                if next_agent:
                    async for result in agent_move():
                        yield result


async def make_move():
    """Handle human move or trigger agent move if it's an agent's turn"""
    current_turn = GAME.board.get_turn()

    # Clear the instruction and fraction displays
    prompt_clears = clear_prompt_displays()

    # Check if it's an agent's turn
    if (current_turn == 'white' and WHITE_AGENT is not None) or (
        current_turn == 'black' and BLACK_AGENT is not None
    ):
        async for result in agent_move():
            yield result
        return

    # Human move logic
    thinking_text = ''
    async for kind, payload in GAME.decide_move():
        # ───────── live-streamed "thinking" lines ──────────
        if kind in ('debate', 'status'):
            thinking_text += payload + '\n'
            dummy_updates = [gr.update()] * 64
            yield (
                dummy_updates
                + [
                    gr.update(),  # turn
                    gr.update(value=thinking_text),  # thinking
                    gr.update(),  # white health
                    gr.update(),  # black health
                    gr.update(),  # jester slot
                ]
                + prompt_clears
            )

        # ───────── King finally chose a move ──────────
        elif kind == 'move':
            move = payload
            GAME.board.apply_move(move)

            white_hp, black_hp = GAME.get_health_scores()
            jester = await GAME.get_jester_comment()

            popup_body = (
                f'<div>'
                f'🃏 <b>{jester.joke_output}</b><br/>'
                f'<i>{jester.judgement.value.title()}</i>'
                f'</div>'
            )
            # random position (10–80 vh, 5–70 vw)
            top_vh, left_vw = random.randint(10, 80), random.randint(5, 70)
            popup_html = (
                f'<div class="jester-popup" '
                f'style="top:{top_vh}vh; left:{left_vw}vw;">'
                f'{popup_body}</div>'
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
                    GAME.board.get_turn(),  # turn
                    gr.update(value=thinking_text),  # thinking
                    gr.update(value=white_hp),  # white health
                    gr.update(value=black_hp),  # black health
                    gr.update(value=popup_html, visible=True),
                ]
                + prompt_clears
            )
            yield outputs

            # keep it visible 5 s
            await asyncio.sleep(5)
            yield (
                [gr.update()] * (64 + 4)  # board + turn + thinking + 2 bars
                + [gr.update(visible=False)]  # hide jester
                + prompt_clears
            )

            # If the next turn is an agent's turn, trigger it
            next_turn = GAME.board.get_turn()
            if (next_turn == 'white' and WHITE_AGENT is not None) or (
                next_turn == 'black' and BLACK_AGENT is not None
            ):
                async for result in agent_move():
                    yield result


def choose_piece(row, col):
    if GAME is None:
        return [gr.update()] * (3 + 64)  # Return empty updates if game not initialized

    piece = GAME.board.piece_at(7 - col, row)
    assert piece is not None
    piece_name = SHORT_PIECE_MAP[piece.lower()]
    turn = GAME.board.get_turn()
    prompt = GAME.get_fraction_user_prompt(turn, piece_name)

    updates = []
    for r in range(8):
        for c in range(7, -1, -1):
            updates.append(gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r), piece)))

    return [
        gr.update(
            value=PIECES[piece.lower()],
            elem_classes=['figure-img', f'cell-{turn}-fg'],
        ),
        prompt,
        piece_name,
    ] + updates


def save_prompt(new_prompt: str, selected: str | None):
    if selected is None or GAME is None:
        return
    GAME.update_fraction_prompt(GAME.board.get_turn(), selected, new_prompt)


def make_board(selected_piece, prompt_img, prompt):
    buttons = []
    with gr.Column():
        with gr.Row():
            health_white = gr.Slider(
                minimum=0,
                maximum=49,
                step=1,
                value=49,
                interactive=False,
                label='White health',
                elem_classes=['thermo', 'health-white'],
            )
            health_black = gr.Slider(
                minimum=0,
                maximum=49,
                step=1,
                value=49,
                interactive=False,
                label='Black health',
                elem_classes=['thermo', 'health-black'],
            )
        with gr.Row() as chess_board:
            with gr.Column(min_width=24, scale=0):
                for rank in range(8, 0, -1):
                    gr.Markdown(f'# {rank}', elem_classes=['rank-file-label'])
            for file in range(8):
                with gr.Column(min_width=70, scale=0):
                    for rank in range(7, -1, -1):
                        buttons.append(
                            gr.Button(
                                value='',
                                interactive=False,
                                elem_classes=[
                                    'cell',
                                    ['cell-black-bg', 'cell-white-bg'][(file + rank) % 2],
                                ],
                            )
                        )

        with gr.Row():
            gr.Markdown(' ')
            for file in range(8):
                letter = chr(ord('a') + file)
                gr.Markdown(f'# {letter}', elem_classes=['rank-file-label'])
    for idx, btn in enumerate(buttons):
        r, c = divmod(idx, 8)
        btn.click(
            fn=partial(choose_piece, r, c),
            outputs=[prompt_img, prompt, selected_piece] + buttons,
            queue=False,
        )
    return buttons, health_white, health_black


def main():
    with gr.Blocks(css=CSS) as demo:
        selected_piece = gr.State(None)

        gr.Markdown('### Prompt Chess')

        # Game Mode Selection
        with gr.Row():
            game_mode_dropdown = gr.Dropdown(
                choices=[mode.value for mode in GameMode],
                value=GameMode.HUMAN_VS_HUMAN.value,
                label='Game Mode',
                elem_classes=['mode-selector'],
            )
            start_game_button = gr.Button('Start Game')

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        prompt_img = gr.Textbox(
                            label='Fraction', interactive=False, elem_classes=['figure-img']
                        )
                    with gr.Column(scale=1):
                        with gr.Row():
                            turn = gr.Textbox(
                                label='Turn',
                                value='',  # Will be set on game initialization
                                interactive=False,
                            )
                        with gr.Row():
                            prompt = gr.Textbox(label='Instructions', interactive=True)
                            prompt.change(
                                fn=save_prompt,
                                inputs=[prompt, selected_piece],
                                outputs=None,
                                queue=False,
                            )
                        with gr.Row():
                            move = gr.Button(value='Make move')
                with gr.Row():
                    thinking = gr.Markdown(label='Thinking…')
                with gr.Row():
                    jester_box = gr.Markdown('', visible=False)  # visibility toggled by make_move

            with gr.Column(min_width=760, scale=0):
                with gr.Row():
                    chess_board, health_white, health_black = make_board(
                        selected_piece, prompt_img, prompt
                    )

            # Initialize game when start button is clicked
            start_game_button.click(
                fn=initialize_game,
                inputs=[game_mode_dropdown],
                outputs=chess_board + [turn, thinking, health_white, health_black, jester_box],
                queue=True,
            )

            # Make move button
            move.click(
                fn=make_move,
                outputs=chess_board
                + [
                    turn,
                    thinking,
                    health_white,
                    health_black,
                    jester_box,
                    prompt_img,
                    prompt,
                ],
                queue=True,
            )

    demo.queue()
    demo.launch()


if __name__ == '__main__':
    main()
