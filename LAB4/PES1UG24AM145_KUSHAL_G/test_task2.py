import unittest, builtins, io, contextlib
from board import initial_board
from game import Checkers
from rules import has_legal_move


def empty():
    return [["."] * 8 for _ in range(8)]


def play(board, player, moves):
    """Run a game from `board`. Input is exactly `moves`; asking for more raises."""
    it = iter(moves)
    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("game asked for input after it should have ended")
    builtins.input = fake_input
    g = Checkers()
    g.board, g.player = board, player
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        g.run()
    return g, buf.getvalue()


class GameOverTests(unittest.TestCase):
    def test_no_pieces_left_ends_game(self):
        b = empty(); b[4][5], b[3][4] = "R", "B"
        g, out = play(b, "R", ["4 5 2 3"])          # R captures B's last piece
        self.assertIn("B has no pieces left. R wins!", out)
        self.assertEqual(g.board[3][4], ".")         # Task 1 still holds

    def test_no_pieces_left_for_red(self):
        b = empty(); b[2][3], b[3][4] = "B", "R"     # B at (2,3) jumps R at (3,4)
        g, out = play(b, "B", ["2 3 4 5"])
        self.assertIn("R has no pieces left. B wins!", out)
        self.assertEqual(g.board[3][4], ".")

    def test_blocked_black_has_no_legal_moves(self):
        b = empty()
        b[0][1] = "B"                                # B stuck in the corner area
        b[1][0], b[1][2], b[2][3] = "R", "R", "R"    # both diagonals blocked, jump landing blocked
        b[6][5] = "R"                                # R's free move
        g, out = play(b, "R", ["6 5 5 4"])
        self.assertIn("B has no legal moves. R wins!", out)

    def test_blocked_red_has_no_legal_moves(self):
        b = empty()
        b[7][0] = "R"
        b[6][1], b[5][2] = "B", "B"                  # block step and jump
        b[1][2] = "B"                                # B's free move
        g, out = play(b, "B", ["1 2 2 3"])
        self.assertIn("R has no legal moves. B wins!", out)

    def test_game_continues_when_opponent_has_a_move(self):
        g, out = play(initial_board(), "R", ["5 4 4 5", "q"])
        self.assertNotIn("Game over", out)
        self.assertEqual(g.player, "B")

    def test_capture_only_move_counts_as_legal(self):
        b = empty()
        b[3][0], b[4][1] = "B", "R"                  # B's only move is the jump to (5,2)
        self.assertTrue(has_legal_move(b, "B"))

    def test_blocked_position_has_no_legal_move(self):
        b = empty()
        b[0][1] = "B"; b[1][0] = b[1][2] = b[2][3] = "R"
        self.assertFalse(has_legal_move(b, "B"))

    def test_empty_side_has_no_legal_move(self):
        self.assertFalse(has_legal_move(empty(), "R"))

    def test_initial_position_both_sides_can_move(self):
        self.assertTrue(has_legal_move(initial_board(), "R"))
        self.assertTrue(has_legal_move(initial_board(), "B"))

    def test_invalid_move_does_not_end_game_or_switch_turn(self):
        b = empty(); b[0][1] = "B"; b[1][0] = b[1][2] = b[2][3] = "R"; b[6][5] = "R"
        g, out = play(b, "R", ["6 5 4 3", "q"])      # illegal: two-row non-jump
        self.assertNotIn("Game over", out)
        self.assertEqual(g.player, "R")

    def test_bad_input_and_quit_still_work(self):
        g, out = play(initial_board(), "R", ["a b c d", "1 2", "9 9 9 9", "q"])
        self.assertIn("Coordinates must be numbers.", out)
        self.assertIn("Enter four coordinates.", out)
        self.assertIn("Outside board.", out)
        self.assertNotIn("Game over", out)

    def test_game_over_prints_final_board_once(self):
        b = empty(); b[4][5], b[3][4] = "R", "B"
        g, out = play(b, "R", ["4 5 2 3"])
        self.assertEqual(out.count("Game over"), 1)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("Game over"))


if __name__ == "__main__":
    unittest.main(verbosity=2)