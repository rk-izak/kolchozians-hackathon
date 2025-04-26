import asyncio

from .game_state import GameState, FRACTION_PIECE_TYPES
from .game_agents.prompt_agent import PromptAgent
from .utils import log_info, log_warning, log_error

WHITE_MODEL = "o4-mini-2025-04-16"
BLACK_MODEL = "o4-mini-2025-04-16"

MAX_TURNS = 15 # Limit game length

async def run_simulation():
    """Runs a game simulation between two PromptAgents."""
    log_info("--- Starting PromptAgent vs PromptAgent Simulation ---")

    # 1. Initialize GameState
    game = GameState()

    # 2. Initialize PromptAgents
    try:
        white_agent = PromptAgent(color='white', model=WHITE_MODEL)
        black_agent = PromptAgent(color='black', model=BLACK_MODEL)
    except Exception as e:
        log_error(f"Failed to initialize agents: {e}", exc_info=True)
        return

    log_info(f"White Agent: {WHITE_MODEL}")
    log_info(f"Black Agent: {BLACK_MODEL}")

    # 3. Game Loop
    turn_count = 1
    while not game.is_game_over() and turn_count <= MAX_TURNS:
        current_color = game.get_current_turn()
        log_info(f"\n--- {current_color.upper()}'S TURN ({turn_count}) ---")

        agent = white_agent if current_color == 'white' else black_agent
        opponent_color = 'black' if current_color == 'white' else 'white'

        # 4a. Get current prompts
        current_prompts_self = {
            ptype: game.get_fraction_user_prompt(current_color, ptype) or ""
            for ptype in FRACTION_PIECE_TYPES
        }

        # 4b. Agent decides on a single prompt update
        log_info(f"Requesting prompt update decision from {current_color} agent...")
        single_update = await agent.decide_single_prompt_update(
            game.board,
            current_prompts_self
            # Pass opponent prompts if the agent signature requires it again
        )

        # 4c. Apply the prompt update if one was decided
        if single_update:
            log_info(f"{current_color.capitalize()} Agent Reasoning: {single_update.reasoning}")
            log_info(f"Updating prompt for {current_color} {single_update.piece_type}: '{single_update.new_prompt}'")
            success = game.update_fraction_prompt(
                current_color,
                single_update.piece_type,
                single_update.new_prompt
            )
            if not success:
                log_warning(f"Failed to apply prompt update for {current_color} {single_update.piece_type}.")
        else:
            log_info(f"{current_color.capitalize()} Agent decided not to update any prompt this turn.")

        # 4d. Run the fraction debate and get King's move decision
        log_info("Starting fraction debate and King decision...")
        chosen_move = None
        try:
            async for kind, payload in game.decide_move():
                if kind == "status":
                    log_info(f"Game Status: {payload}")
                elif kind == "debate":
                    # Log debate snippets if desired (can be verbose)
                    # log_info(f"Debate Update: {payload}")
                    pass # Often too verbose to log everything
                elif kind == "move":
                    chosen_move = payload
                    log_info(f"King decided move: {chosen_move}")
                    break # Move decided
        except Exception as e:
             log_error(f"Error during game.decide_move(): {e}", exc_info=True)
             break # Stop simulation on error

        # 4e. Apply the chosen move
        if chosen_move:
            success, message = game.apply_move(chosen_move)
            if success:
                log_info(f"Applied move {chosen_move}. Board updated.")
                game.print_board()

                # 4g. Check game end conditions
                status = game.get_game_status()
                if status['is_checkmate']:
                    log_info(f"CHECKMATE! {status['winner']} wins.")
                    break
                elif status['is_stalemate']:
                    log_info("STALEMATE!")
                    break
                elif status['is_insufficient_material']:
                    log_info("DRAW by insufficient material.")
                    break
                elif status['is_seventyfive_moves']:
                    log_info("DRAW by seventy-five moves rule.")
                    break
                elif status['is_fivefold_repetition']:
                    log_info("DRAW by fivefold repetition.")
                    break
                elif status['is_check']:
                    log_info("Check!")
            else:
                log_error(f"!!! Failed to apply legally chosen move '{chosen_move}': {message} - Simulation Halted !!!")
                # This often indicates an internal inconsistency
                break
        else:
            log_error("!!! King failed to decide on a move. Simulation Halted. !!!")
            break # Stop simulation

        turn_count += 1
        # Small delay to prevent overwhelming APIs if using external models rapidly
        await asyncio.sleep(0.5)


    # 5. Game End Summary
    if turn_count > MAX_TURNS:
        log_info(f"\n--- Simulation Ended: Max turns ({MAX_TURNS}) reached ---")
    elif not game.is_game_over():
         log_info("\n--- Simulation Halted Prematurely (Error) ---")
    else:
        log_info("\n--- Simulation Ended: Game Over ---")
        # Log final status if not already checkmate/stalemate
        final_status = game.get_game_status()
        if not final_status.get('is_checkmate') and not final_status.get('is_stalemate'):
             log_info(f"Final Result: {final_status.get('result', 'Unknown')}")

    log_info("--- Simulation Complete ---")


if __name__ == "__main__":
    asyncio.run(run_simulation())
