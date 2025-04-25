import gradio as gr

# Example 8×8 board
example_board = [
    ["♜","♞","♝","♛","♚","♝","♞","♜"],
    ["♟"]*8,
    [" "]*8,
    [" "]*8,
    [" "]*8,
    [" "]*8,
    ["♙"]*8,
    ["♖","♘","♗","♕","♔","♗","♘","♖"]
]

css = """
.cell-button {
    width: 70px !important;
    height: 70px !important;
    font-size: 24px !important;
    padding: 0 !important;
}
"""

def make_board(board, out):
    with gr.Row():
        for col in range(8):
            with gr.Column(min_width=70, scale=0): 
                for row in range(8):
                    piece = board[row][col]
                    gr.Button(
                        value=piece,
                        elem_classes=["cell-button"]
                    ).click(
                        fn=lambda r=row, c=col: f"{r},{c}",
                        outputs=out
                    )

with gr.Blocks(css=css) as demo:
    gr.Markdown("### Chessboard as Clickable Grid")
    clicked = gr.Textbox(label="Clicked Square (row,col)", interactive=False)
    with gr.Row():
        with gr.Column(scale=1):
            prompt = gr.Textbox(label="Prompt")
        with gr.Column(min_width=760, scale=0):
            make_board(example_board, clicked)

demo.launch()
