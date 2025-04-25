import gradio as gr

from .logic import Board


CSS = """
.cell-button {
    width: 70px !important;
    height: 70px !important;
    font-size: 48px !important;
    padding: 0 !important;
}
.figure-img textarea {
    font-size: 128px !important;
    text-align: center;
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


def main():
    board = Board()
    # board = chess.Board()
    # print(board)
    with gr.Blocks(css=CSS) as demo:
        gr.Markdown("### Prompt Chess")
        clicked = gr.Textbox(label="Prompt", interactive=False)
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=0):
                        thinking_img = gr.Textbox(label="Figure", interactive=False, elem_classes=["figure-img"])
                    with gr.Column(scale=1):
                        thinking = gr.Textbox(label="Thinking...", interactive=False)
            with gr.Column(min_width=760, scale=0):
                make_board(board, thinking_img, thinking)
    demo.launch()


if __name__ == "__main__":
    main()
