import unittest, builtins, io, contextlib
from board import initial_board, move_piece
from game import Checkers


def play(moves):
    it = iter(moves + ["q"])
    builtins.input = lambda prompt="": next(it)
    g = Checkers()
    with contextlib.redirect_stdout(io.StringIO()):
        g.run()
    return g


def count(board, ch):
    return sum(row.count(ch) for row in board)


class CaptureTests(unittest.TestCase):
    def test_full_sequence_removes_jumped_piece(self):
        g = play(["5 4 4 5", "2 3 3 4", "4 5 2 3"])
        self.assertEqual(g.board[3][4], ".")   # jumped B removed
        self.assertEqual(g.board[4][5], ".")   # R's start square empty
        self.assertEqual(g.board[2][3], "R")   # R at destination
        self.assertEqual(count(g.board, "B"), 11)
        self.assertEqual(count(g.board, "R"), 12)
        self.assertEqual(g.player, "B")

    def test_expected_full_board(self):
        g = play(["5 4 4 5", "2 3 3 4", "4 5 2 3"])
        expected = [
            ". B . B . B . B",
            "B . B . B . B .",
            ". B . R . B . B",
            ". . . . . . . .",
            ". . . . . . . .",
            "R . R . . . R .",
            ". R . R . R . R",
            "R . R . R . R .",
        ]
        self.assertEqual([" ".join(r) for r in g.board], expected)

    def test_captured_piece_cannot_be_captured_again(self):
        from rules import capture_move
        b = [["."] * 8 for _ in range(8)]
        b[4][5], b[3][4] = "R", "B"
        move_piece(b, (4, 5), (2, 3))
        self.assertEqual(b[3][4], ".")
        b[4][3] = "R"  # a second R that would have jumped (3,4) toward (2,5)
        self.assertFalse(capture_move(b, "R", (4, 3), (2, 5)))

    def test_jumping_empty_square_is_rejected(self):
        g = play(["5 2 3 4"])  # (4,3) is empty, so there is nothing to jump
        self.assertEqual(g.board, initial_board())
        self.assertEqual(g.player, "R")

    def test_ordinary_move_removes_nothing(self):
        g = play(["5 4 4 5"])
        self.assertEqual(count(g.board, "R"), 12)
        self.assertEqual(count(g.board, "B"), 12)

    def test_move_piece_simple_step_untouched(self):
        b = initial_board()
        move_piece(b, (5, 0), (4, 1))
        self.assertEqual(b[4][1], "R")
        self.assertEqual(count(b, "R"), 12)

    def test_invalid_move_changes_nothing(self):
        g = play(["5 4 3 6"])
        self.assertEqual(g.board, initial_board())
        self.assertEqual(g.player, "R")


if __name__ == "__main__":
    unittest.main(verbosity=2)