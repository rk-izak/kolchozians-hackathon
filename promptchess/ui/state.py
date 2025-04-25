
import re
import uuid

class State():
    def __init__(self, name):
        self.name = name
        self.description = uuid.uuid4()

    def visualize(self):
        match re.sub(r'\d+', '', self.name):
            case 'p':
                return '♟'
            case 'P':
                return '♙'
            case 'r':
                return '♜'
            case 'R':
                return '♖'
            case 'b':
                return '♝'
            case 'B':
                return '♗'
            case 'q':
                return '♛'
            case 'Q':
                return '♕'
            case 'k':
                return '♚'
            case 'K':
                return '♔'
            case 'n':
                return '♞'
            case 'N':
                return '♘'
            case '.':
                return ''


class Board():
    def __init__(self):
        self.board = []
        for _ in range(8):
            self.board.append([State('.') for _ in range(8)])
        
        for col in range(8):
            self.board[6][col] = State(f'p{col}')
            self.board[1][col] = State(f'P{col}')
    
        self.board[0][0] = State(f'R{0}')
        self.board[0][7] = State(f'R{7}')
        self.board[7][0] = State(f'r{0}')
        self.board[7][7] = State(f'r{7}')


        self.board[0][1] = State(f'N{1}')
        self.board[0][6] = State(f'N{6}')
        self.board[7][1] = State(f'n{1}')
        self.board[7][6] = State(f'n{6}')


        self.board[0][2] = State(f'B{2}')
        self.board[0][5] = State(f'B{5}')
        self.board[7][2] = State(f'b{2}')
        self.board[7][5] = State(f'b{5}')
    

        self.board[0][3] = State(f'Q{3}')
        self.board[0][4] = State(f'K{4}')
        self.board[7][3] = State(f'q{3}')
        self.board[7][4] = State(f'k{4}')