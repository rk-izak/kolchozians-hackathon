from pathlib import Path

import chess
import pygame


MAX_FPS = 30
BOARD_WIDTH = 560
BOARD_HEIGHT = 560

SQ_SIZE = BOARD_WIDTH / 8

COLORS = [pygame.Color('#EBEBD0'), pygame.Color('#769455')]

IMAGES = {}


def load_images():
    pieces = [
        "P", "R", "N", "B", "Q", "K",
        "p", "r", "n", "b", "q", "k",
    ]
    images_path = Path(__file__).parent / "images"
    for piece in pieces:
        IMAGES[piece] = pygame.transform.smoothscale(
            pygame.image.load(images_path / f"{piece}.png"),
            (SQ_SIZE, SQ_SIZE),
        )


def draw(screen, board):
    # Draw board
    for y in range(8):
        for x in range(8):
            color = COLORS[((x + y) % 2)]
            pygame.draw.rect(screen, color, pygame.Rect(x * SQ_SIZE, y * SQ_SIZE, SQ_SIZE, SQ_SIZE))

    # Draw pieces
    for y in range(8):
        for x in range(8):
            piece = board.piece_at(chess.square(y, x))
            if piece is None:
                continue
            piece = str(piece)
            screen.blit(IMAGES[piece], pygame.Rect(x * SQ_SIZE, y * SQ_SIZE, SQ_SIZE, SQ_SIZE))


def main():
    load_images()

    screen = pygame.display.set_mode((BOARD_WIDTH, BOARD_HEIGHT))
    clock = pygame.time.Clock()
    screen.fill(pygame.Color('white'))

    board = chess.Board()
    # print(dir(chess))
    # print("=" * 80)
    # print(dir(board))
    # print(board)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        draw(screen, board)

        clock.tick(MAX_FPS)
        pygame.display.flip()

    return


if __name__ == "__main__":
    main()
