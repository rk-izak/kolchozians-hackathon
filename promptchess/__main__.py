import gradio as gr

from .logic import Board


CSS = """
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


def main():
    board = Board()
    # board = chess.Board()
    # print(board)
    with gr.Blocks(css=CSS) as demo:
        gr.Markdown("### PromptChess")
        _ = gr.Textbox(label="Clicked Square (row,col)", interactive=False)
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    thinking_img = gr.Textbox(label="Figure", elem_classes=["figure-img"])
                    thinking = gr.Textbox(label="Thinking...", interactive=False, elem_classes=["figure-img"])
            with gr.Column(min_width=760, scale=0):
                make_board(board, thinking_img, thinking)

    demo.launch()


if __name__ == "__main__":
    main()
