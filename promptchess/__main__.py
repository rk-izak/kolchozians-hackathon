import asyncio
import random
import gradio as gr
from functools import partial
from enum import Enum
from pathlib import Path

from .game_state import GameState, SHORT_PIECE_MAP, EFFICIENT_MODEL
from .game_agents.prompt_agent import PromptAgent


class GameMode(Enum):
    HUMAN_VS_HUMAN = "Human vs Human"
    HUMAN_VS_AGENT = "Human vs Agent"
    AGENT_VS_AGENT = "Agent vs Agent"


PIECES = {
    "p": "♟", "r": "♜", "b": "♝",
    "q": "♛", "k": "♚", "n": "♞",
}

CSS = """
body {
    font-family: Arial, sans-serif;
}
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

/* —— Ruleset list font —— */
.ruleset-list {
  font-size: 30px;
}

/* —— Legend symbol sizing —— */
.legend-symbol { font-size: 32px; text-align: center; }
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
        BLACK_AGENT = PromptAgent(color="black", model=EFFICIENT_MODEL)
        WHITE_AGENT = None
    elif CURRENT_GAME_MODE == GameMode.AGENT_VS_AGENT:
        WHITE_AGENT = PromptAgent(color="white", model=EFFICIENT_MODEL)
        BLACK_AGENT = PromptAgent(color="black", model=EFFICIENT_MODEL)
    else:
        WHITE_AGENT = None
        BLACK_AGENT = None

    GAME = GameState()

    board_updates = []
    for r in range(8):
        for c in range(7, -1, -1):
            board_updates.append(
                gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r)))
            )

    return board_updates + [
        gr.update(value=GAME.board.get_turn().title()),  # turn (capitalized)
        gr.update(value="Game initialized with mode: " + game_mode),  # thinking
        gr.update(value=49),  # white health
        gr.update(value=49),  # black health
        gr.update(visible=False),  # jester box
    ]


def get_cell_properties(rank: int, file: int, piece: str | None, selected_piece: str | None = None) -> dict:
    classes = ["cell", ["cell-black-bg", "cell-white-bg"][(file + rank) % 2]]
    if piece is not None:
        classes.append("cell-black-fg" if piece.islower() else "cell-white-fg")
        if selected_piece is not None and piece == selected_piece:
            classes.append("cell-border")

    if piece is None:
        interactive = False
    elif piece.lower() == "k":
        interactive = False
    else:
        current_turn = GAME.board.get_turn()
        is_user_turn = True

        if current_turn == "white" and WHITE_AGENT is not None:
            is_user_turn = False
        elif current_turn == "black" and BLACK_AGENT is not None:
            is_user_turn = False

        interactive = (
            is_user_turn and
            (current_turn == "white" and piece.isupper() or
             current_turn == "black" and piece.islower())
        )

    return {
        "value": PIECES[piece.lower()] if piece is not None else "",
        "interactive": interactive,
        "elem_classes": classes,
    }


def clear_prompt_displays():
    return [
        gr.update(value=""),  # prompt_img
        gr.update(value=""),  # prompt
    ]


async def agent_move(prompt_updates=None):
    current_turn = GAME.board.get_turn()
    agent = WHITE_AGENT if current_turn == "white" else BLACK_AGENT
    thinking_text = ""

    if prompt_updates is None and CURRENT_GAME_MODE != GameMode.HUMAN_VS_HUMAN:
        thinking_text += f"Agent ({current_turn.title()}) is deciding on a prompt update...\n"
        prompt_clears = clear_prompt_displays()
        dummy_updates = [gr.update()] * 64
        yield dummy_updates + [
            gr.update(),                               # turn
            gr.update(value=thinking_text),            # thinking
            gr.update(),                               # white health
            gr.update(),                               # black health
            gr.update(),                               # jester slot
        ] + prompt_clears

        current_prompts = {}
        for piece_type in ["pawn", "knight", "bishop", "rook", "queen"]:
            prompt = GAME.get_fraction_user_prompt(current_turn, piece_type)
            if prompt:
                current_prompts[piece_type] = prompt

        try:
            prompt_updates = await agent.decide_single_prompt_update(
                GAME.board, current_prompts
            )
            if prompt_updates:
                thinking_text += f"Agent ({current_turn.title()}) updated {prompt_updates.piece_type} prompt: {prompt_updates.new_prompt}\n"
                thinking_text += f"Reasoning: {prompt_updates.reasoning}\n\n"
        except Exception as e:
            thinking_text += f"Error getting prompt update: {e}\n\n"

    if prompt_updates:
        piece_type = prompt_updates.piece_type
        new_prompt = prompt_updates.new_prompt
        GAME.update_fraction_prompt(current_turn, piece_type, new_prompt)
        if "updated" not in thinking_text:
            thinking_text += f"Agent ({current_turn.title()}) updated {piece_type} prompt: {new_prompt}\n\n"

    thinking_text += f"Agent ({current_turn.title()}) is deciding on a move...\n"
    async for kind, payload in GAME.decide_move():
        if kind in ("debate", "status"):
            thinking_text += payload + "\n"
            dummy_updates = [gr.update()] * 64
            yield dummy_updates + [
                gr.update(),                          # turn
                gr.update(value=thinking_text),       # thinking
                gr.update(),                          # white health
                gr.update(),                          # black health
                gr.update(),                          # jester slot
            ] + clear_prompt_displays()
        elif kind == "move":
            move = payload
            GAME.board.apply_move(move)
            white_hp, black_hp = GAME.get_health_scores()
            jester = await GAME.get_jester_comment()
            popup_body = (
                f"<div>"
                f"🃏 <b>{jester.joke_output}</b><br/>"
                f"<i>{jester.judgement.value.title()}</i>"
                f"</div>"
            )
            top_vh, left_vw = random.randint(10, 80), random.randint(5, 70)
            popup_html = (
                f'<div class="jester-popup" style="top:{top_vh}vh; left:{left_vw}vw;">'
                f"{popup_body}</div>"
            )
            board_updates = []
            for r in range(8):
                for c in range(7, -1, -1):
                    board_updates.append(
                        gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r)))
                    )
            outputs = board_updates + [
                GAME.board.get_turn().title(),                 # turn (capitalized)
                gr.update(value=thinking_text),                 # thinking
                gr.update(value=white_hp),                      # white health
                gr.update(value=black_hp),                      # black health
                gr.update(value=popup_html, visible=True),      # jester popup
            ] + clear_prompt_displays()
            yield outputs
            await asyncio.sleep(5)
            yield (
                [gr.update()] * (64 + 4)               # board + turn + thinking + 2 bars
                + [gr.update(visible=False)]           # hide jester
                + clear_prompt_displays()
            )
            next_turn = GAME.board.get_turn()
            if (next_turn == "white" and WHITE_AGENT is not None) or (next_turn == "black" and BLACK_AGENT is not None):
                if CURRENT_GAME_MODE == GameMode.AGENT_VS_AGENT:
                    await asyncio.sleep(2)
                async for result in agent_move():
                    yield result


async def make_move():
    current_turn = GAME.board.get_turn()
    prompt_clears = clear_prompt_displays()
    if (current_turn == "white" and WHITE_AGENT is not None) or (current_turn == "black" and BLACK_AGENT is not None):
        async for result in agent_move():
            yield result
        return
    thinking_text = ""
    async for kind, payload in GAME.decide_move():
        if kind in ("debate", "status"):
            thinking_text += payload + "\n"
            dummy_updates = [gr.update()] * 64
            yield dummy_updates + [
                gr.update(),                          # turn
                gr.update(value=thinking_text),       # thinking
                gr.update(),                          # white health
                gr.update(),                          # black health
                gr.update(),                          # jester slot
            ] + prompt_clears
        elif kind == "move":
            move = payload
            GAME.board.apply_move(move)
            white_hp, black_hp = GAME.get_health_scores()
            jester = await GAME.get_jester_comment()
            popup_body = (
                f"<div>"
                f"🃏 <b>{jester.joke_output}</b><br/>"
                f"<i>{jester.judgement.value.title()}</i>"
                f"</div>"
            )
            top_vh, left_vw = random.randint(10, 80), random.randint(5, 70)
            popup_html = (
                f'<div class="jester-popup" style="top:{top_vh}vh; left:{left_vw}vw;">'
                f"{popup_body}</div>"
            )
            board_updates = []
            for r in range(8):
                for c in range(7, -1, -1):
                    board_updates.append(
                        gr.update(**get_cell_properties(r, c, GAME.board.piece_at(c, r)))
                    )
            outputs = board_updates + [
                GAME.board.get_turn().title(),                 # turn (capitalized)
                gr.update(value=thinking_text),                 # thinking
                gr.update(value=white_hp),                      # white health
                gr.update(value=black_hp),                      # black health
                gr.update(value=popup_html, visible=True),      # jester popup
            ] + prompt_clears
            yield outputs
            await asyncio.sleep(5)
            yield (
                [gr.update()] * (64 + 4)               # board + turn + thinking + 2 bars
                + [gr.update(visible=False)]           # hide jester
                + prompt_clears
            )
            next_turn = GAME.board.get_turn()
            if (next_turn == "white" and WHITE_AGENT is not None) or (next_turn == "black" and BLACK_AGENT is not None):
                async for result in agent_move():
                    yield result


def choose_piece(row, col):
    if GAME is None:
        return [gr.update()] * (3 + 64)
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
                label="White health",
                elem_classes=["thermo", "health-white"],
            )
            health_black = gr.Slider(
                minimum=0,
                maximum=49,
                step=1,
                value=49,
                interactive=False,
                label="Black health",
                elem_classes=["thermo", "health-black"],
            )
        with gr.Row() as chess_board:
            with gr.Column(min_width=24, scale=0):
                for rank in range(8, 0, -1):
                    gr.Markdown(f"# {rank}", elem_classes=["rank-file-label"])
            for file in range(8):
                with gr.Column(min_width=70, scale=0):
                    for rank in range(7, -1, -1):
                        buttons.append(
                            gr.Button(
                                value="",
                                interactive=False,
                                elem_classes=["cell", ["cell-black-bg", "cell-white-bg"][(file + rank) % 2]]
                            )
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
    return buttons, health_white, health_black


def main():
    with gr.Blocks(css=CSS) as demo:
        # Title
        gr.Markdown("<h1 style='text-align:center; font-size:60px;'>Prompt Chess</h1>")

        # Ruleset Section (as numbered list)
        gr.Markdown(
    """
**Ruleset**
1. After picking from a list of available Game Modes, the game begins  
2. In Human vs Agent/Agent vs Agent, each agent decides its behaviour from aggressive, defensive, and balanced each turn  
3. Players take turns trying to influence their LLM-Ruled Agentic Factions via Prompt Injections, trying to influence the King to make the best decision  
4. After a prompt is written, and **Make move** is clicked (red out-glow), the user sees the Factions debate and final King reasoning and decision  
5. The game continues in turns until either a pre-set number of turns passes, or a checkmate is achieved  
6. Losing a Chess Piece costs health, different pieces have different associated health loss  
7. The winner is decided via final Health score, with the highest being the winner  

Be careful! The King might have a preference towards certain factions, and each faction might have different goals in mind! Check the legend below for more details.
""",
    elem_classes=["ruleset-list"]
)


        selected_piece = gr.State(None)

        # Game Mode Selection
        with gr.Row():
            game_mode_dropdown = gr.Dropdown(
                choices=[mode.value for mode in GameMode],
                value=GameMode.HUMAN_VS_HUMAN.value,
                label="Game Mode",
                elem_classes=["mode-selector"]
            )
            start_game_button = gr.Button("Start Game")

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        prompt_img = gr.Textbox(
                            label="Faction", interactive=False, elem_classes=["figure-img"]
                        )
                    with gr.Column(scale=1):
                        with gr.Row():
                            turn = gr.Textbox(
                                label="Turn",
                                value="",
                                interactive=False,
                            )
                        with gr.Row():
                            prompt = gr.Textbox(label="Court Advice to Faction", interactive=True)
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
                queue=True
            )

            # Make move button
            move.click(
                fn=make_move,
                outputs=chess_board + [
                    turn,
                    thinking,
                    health_white,
                    health_black,
                    jester_box,
                ],
                queue=True,
            )

        # Faction Legend (larger font for symbols)
        with gr.Row():
            with gr.Column():
                gr.Markdown("## Faction Legend")
                gr.Markdown(
                    """
<div style="font-size:16px;">
<table style="width:100%; table-layout: fixed;">
  <colgroup>
    <col style="width:100px;">
    <col style="width:150px;">
    <col style="width:100px;">
    <col style="width:auto;">
  </colgroup>
  <thead>
    <tr><th>Symbol</th><th>Faction</th><th>Health Loss</th><th>Behaviour</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="legend-symbol">♟</td><td>Pawn</td><td>1</td><td>Simple-minded but earnest and eager for valor, loyal to higher ranks, look up to Knights and Rooks for guidance, form close camaraderie with each other, address sovereigns with awe, resent enemy pawns that block their advance.</td>
    </tr>
    <tr>
      <td class="legend-symbol">♞</td><td>Knight</td><td>3</td><td>Bold, adventurous, and slightly boastful, delights in playful banter and heroic tales, protects Pawns as “little brothers,” enjoys friendly rivalry with fellow Knights, teams up with Bishops’ wisdom, pledges absolute fealty to both King and Queen.</td>
    </tr>
    <tr>
      <td class="legend-symbol">♝</td><td>Bishop</td><td>3</td><td>Watchful, contemplative, and subtly shrewd advisor who speaks little but observes much, guided by duty to a higher cause, offers calm counsel to the King, coordinates stratagems with the Queen, values Knights’ mobility, keeps a wary distance from his opposing counterpart.</td>
    </tr>
    <tr>
      <td class="legend-symbol">♜</td><td>Rook</td><td>5</td><td>Stoic, disciplined, and slow to anger, sees the board as walls and corridors to police, speaks only in short, weighty statements, shields the King, cooperates closely with fellow Rook, provides backbone for advancing Pawns, distrusts Queen’s reckless opening of files.</td>
    </tr>
    <tr>
      <td class="legend-symbol">♛</td><td>Queen</td><td>9</td><td>Decisive, strategic, and commanding, balances charisma with strict authority, values every piece’s role, demands instant obedience from Pawns, employs Knights for swift strikes, relies on Bishops’ foresight, partners warmly with King, regards opposing Queen as true equal and rival.</td>
    </tr>
    <tr>
      <td class="legend-symbol">♚</td><td>King</td><td>N/A (Game Over)</td><td>Cautious and measured, bears the realm’s burden, values survival over personal glory, grants quiet encouragement to loyal subjects, trusts Rooks to fortify his position, heeds Bishops’ guidance, admires Knights’ valor, honors Pawns’ sacrifices, relies on Queen as chief defender and strategist.</td>
    </tr>
  </tbody>
</table>
</div>
"""
                )

    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
