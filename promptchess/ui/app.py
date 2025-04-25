import gradio as gr
from state import Board

css = """
.cell-button {
    width: 70px !important;
    height: 70px !important;
    font-size: 48px !important;
    padding: 0 !important;
}
.figure-img {
    font-size: 128px !important;
}
"""

def make_board(board, thinking_img, thinking):
    with gr.Row():
        for col in range(8):
            with gr.Column(min_width=70, scale=0): 
                for row in range(8):
                    piece = board.board[row][col].visualize()
                    gr.Button(
                        value=piece,
                        elem_classes=["cell-button"]
                    ).click(
                        fn=lambda r=row, c=col: (board.board[r][c].visualize(), board.board[r][c].description),
                        outputs=(thinking_img, thinking)
                    )

with gr.Blocks(css=css) as demo:
    gr.Markdown("### Prompt Chess")
    clicked = gr.Textbox(label="Clicked Square (row,col)", interactive=False)
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Row():
                thinking_img = gr.Textbox(label="Figure", elem_classes=["figure-img"])
                thinking = gr.Textbox(label="Thinking...", interactive=False, elem_classes=["figure-img"])
        with gr.Column(min_width=760, scale=0):
            make_board(Board(), thinking_img, thinking)

demo.launch()
