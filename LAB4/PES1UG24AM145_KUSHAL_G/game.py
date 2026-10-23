from board import initial_board, move_piece, SIZE
from rules import (simple_move, capture_move, promote, has_legal_move,
                   has_capture, player_has_capture)


def _describe_move(piece, start, end, jumped, crowned, jump_again):
    """Build the single player-facing result line for one accepted move."""
    route = f"({start[0]},{start[1]}) -> ({end[0]},{end[1]})"
    if jumped:
        kind, (jr, jc) = jumped
        text = f"{piece} captures {kind} at ({jr},{jc}): {route}."
    else:
        text = f"{piece} moves {route}."
    if crowned:
        text += f" Promoted to king: {crowned} at ({end[0]},{end[1]})."
    if jump_again:
        text += f" Jump again from ({end[0]},{end[1]})."
    return text


class Checkers:
    def __init__(self):
        self.board = initial_board()
        self.player = "R"
        self.chain = None  # (row, col) of a piece that must keep capturing

    def print_board(self):
        print("\n   " + " ".join(str(c) for c in range(SIZE)))
        for r, row in enumerate(self.board):
            print(f"{r}  " + " ".join(row))

    def _check_game_over(self):
        """Return a result message if the player to move has lost, else None."""
        winner = "B" if self.player == "R" else "R"
        if not any(cell in (self.player, self.player + "K")
                   for row in self.board for cell in row):
            return f"Game over: {self.player} has no pieces left. {winner} wins!"
        if not has_legal_move(self.board, self.player):
            return f"Game over: {self.player} has no legal moves. {winner} wins!"
        return None

    def run(self):
        print("Checkers — move: sr sc er ec")
        while True:
            self.print_board()
            raw = input(f"{self.player}> ").strip().lower().split()
            if raw == ["q"]:
                return
            if len(raw) != 4:
                print("Enter four coordinates.")
                continue
            try:
                sr, sc, er, ec = map(int, raw)
            except ValueError:
                print("Coordinates must be numbers.")
                continue
            if not all(0 <= x < SIZE for x in (sr, sc, er, ec)):
                print("Outside board.")
                continue
            if self.board[sr][sc] not in (self.player, self.player + "K"):
                print("That is not your piece.")
                continue

            start, end = (sr, sc), (er, ec)
            captured = capture_move(self.board, self.player, start, end)

            if self.chain and not (start == self.chain and captured):
                print(f"You must keep capturing with the piece at "
                      f"{self.chain[0]} {self.chain[1]}.")
                continue
            if not captured:
                if not simple_move(self.board, self.player, start, end):
                    print("Invalid move.")
                    continue
                if player_has_capture(self.board, self.player):
                    print("Capture is mandatory.")
                    continue

            piece = self.board[sr][sc]
            jumped = None
            if captured:
                mr, mc = (sr + er) // 2, (sc + ec) // 2
                jumped = (self.board[mr][mc], (mr, mc))

            move_piece(self.board, start, end)
            promote(self.board)
            promoted = not piece.endswith("K") and self.board[er][ec].endswith("K")

            # Multi-capture: the same piece keeps jumping, unless it was just crowned.
            jump_again = (captured and not promoted
                          and has_capture(self.board, self.player, end))

            # Exactly one result line per accepted move.
            print(_describe_move(piece, start, end, jumped,
                                 self.board[er][ec] if promoted else None,
                                 jump_again))

            if jump_again:
                self.chain = end
                continue

            self.chain = None
            self.player = "B" if self.player == "R" else "R"

            result = self._check_game_over()
            if result:
                self.print_board()
                print(result)
                return