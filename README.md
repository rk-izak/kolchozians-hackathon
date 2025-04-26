# PromptChess

[OpenAI x AI Tinkerers Hackathon - Warsaw!](https://warsaw.aitinkerers.org/p/openai-x-ai-tinkerers-hackathon-warsaw) kolchozians-hackathon project.

## Overview

`promptchess` is a Python module implementing a novel chess variant where the behavior of different piece types (fractions) can be influenced by natural language prompts. AI agents can play the game and even modify these prompts during gameplay based on their reasoning.

### Features

*   **Prompt-driven Behavior:** Define or let AI modify prompts that guide how piece fractions behave.
*   **Multiple Game Modes:**
    *   Human vs Human
    *   Human vs AI Agent
    *   AI Agent vs AI Agent (Simulation)
*   **Gradio Interface:** Play interactively via a web interface.
*   **Simulation Mode:** Run non-interactive games between AI agents.

### Setup

This project uses Poetry for dependency management.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/rk-izak/kolchozians-hackathon.git
    cd kolchozians-hackathon
    ```
2.  **Install dependencies:**
    ```bash
    poetry install
    ```
3.  **Set up Environment Variables:** (If using AI agents that require API keys, e.g., OpenAI)
    Create a `.env` file in the root directory and add your API key:
    ```env
    # Example for OpenAI
    OPENAI_API_KEY=your_openai_api_key_here
    OPIK_API_KEY=your_opik_api_key_here
    OPIK_WORKSPACE=your_opik_workspace
    ```
    *Note: The specific environment variables needed may depend on the `PromptAgent` implementation.*

### Running PromptChess

#### Interactive Mode (Gradio UI)

To launch the interactive web interface:

```bash
poetry run python -m promptchess
```

This will start a local web server, and you can access the game interface in your browser (usually at `http://127.0.0.1:7860`). Select the desired game mode from the interface.

#### Simulation Mode

To run a non-interactive simulation between two AI agents (as defined in `promptchess/simulation.py`):

```bash
poetry run python promptchess/simulation.py
```

The simulation progress and results will be printed to the console.

### How it Works

1.  **Game State:** The `GameState` class manages the overall chess game, including the board state, turn management, and rules.
2.  **Fractions & Prompts:** Each piece type (Pawn, Rook, Knight, Bishop, Queen - excluding the King) represents a "fraction". Each fraction for each player can have an associated natural language "user prompt" stored within the `GameState`.
3.  **AI Agents (`PromptAgent`):** These agents interact with Large Language Models (LLMs).
    *   **Prompt Updates:** Before making a move, an agent can analyze the game state and decide to *update* the prompt for one of its piece fractions to try and improve its strategy. It provides reasoning for this change.
    *   **Move Decisions:** The core move generation involves an internal "debate" process (managed by `GameState.decide_move`). This process likely involves the LLMs associated with each fraction (using their current prompts) contributing to the decision-making, ultimately leading the King to choose the final move.
4.  **Gameplay Loop:**
    *   The current player's agent (if applicable) decides whether to update a fraction's prompt.
    *   The `GameState` facilitates the "debate" among the current player's fractions based on their prompts.
    *   The King fraction makes the final move decision.
    *   The move is applied, and the turn switches.
    *   The game continues until a checkmate, stalemate, draw condition, or maximum turn limit is reached.

The `__main__.py` script handles the Gradio interface logic, allowing human players to interact, view the board, select pieces, and manage prompts (if playing as human). The `simulation.py` script runs a headless game between two agents, logging the process.
