import unittest, builtins, io, contextlib
from board import initial_board
from game import Checkers
from rules import capture_move, simple_move, has_legal_move, promote


def empty():
    return [["."] * 8 for _ in range(8)]


def make(**pieces):
    """make(R=[(r,c),...], RK=[...], B=[...], BK=[...]) -> board."""
    b = empty()
    for piece, squares in pieces.items():
        for r, c in squares:
            b[r][c] = piece
    return b


def play(board, player, moves):
    """Run from `board`; a final 'q' is appended so unfinished games quit cleanly."""
    it = iter(moves + ["q"])
    builtins.input = lambda prompt="": next(it)
    g = Checkers()
    g.board, g.player = board, player
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        g.run()
    return g, buf.getvalue()


def snapshot(b):
    return [row[:] for row in b]


class ForcedCaptureTests(unittest.TestCase):
    def test_ordinary_move_rejected_when_capture_available(self):
        b = make(R=[(4, 5), (6, 1)], B=[(3, 4), (0, 1)])
        before = snapshot(b)
        g, out = play(b, "R", ["6 1 5 0"])
        self.assertIn("Capture is mandatory.", out)
        self.assertEqual(g.board, before)
        self.assertEqual(g.player, "R")

    def test_capturing_move_is_accepted(self):
        b = make(R=[(4, 5), (6, 1)], B=[(3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 5 0", "4 5 2 3"])
        self.assertEqual(g.board[3][4], ".")
        self.assertEqual(g.board[2][3], "R")
        self.assertEqual(g.player, "B")

    def test_any_available_capture_may_be_chosen(self):
        b = make(R=[(4, 1), (4, 5)], B=[(3, 0), (3, 4), (0, 7)])
        b[3][2] = "B"                                # R (4,1) can jump (3,2) -> (2,3)
        g, out = play(b, "R", ["4 5 2 3"])           # choose the other capture
        self.assertEqual(g.board[3][4], ".")
        self.assertEqual(g.board[2][3], "R")
        self.assertEqual(g.player, "B")

    def test_forced_capture_applies_to_black(self):
        b = make(B=[(3, 2), (0, 7)], R=[(4, 3), (7, 0)])
        before = snapshot(b)
        g, out = play(b, "B", ["0 7 1 6"])
        self.assertIn("Capture is mandatory.", out)
        self.assertEqual(g.board, before)
        g, out = play(make(B=[(3, 2), (0, 7)], R=[(4, 3), (7, 0)]), "B", ["3 2 5 4"])
        self.assertEqual(g.board[4][3], ".")
        self.assertEqual(g.board[5][4], "B")

    def test_king_backward_capture_makes_capture_mandatory(self):
        b = make(RK=[(4, 3)], R=[(6, 7)], B=[(5, 4), (0, 1)])
        before = snapshot(b)
        g, out = play(b, "R", ["6 7 5 6"])
        self.assertIn("Capture is mandatory.", out)
        self.assertEqual(g.board, before)

    def test_ordinary_move_allowed_when_no_capture(self):
        g, out = play(initial_board(), "R", ["5 4 4 5"])
        self.assertNotIn("mandatory", out)
        self.assertEqual(g.player, "B")

    def test_only_capture_available_does_not_trigger_game_over(self):
        b = make(B=[(3, 0)], R=[(4, 1), (7, 6)])
        g, out = play(b, "B", ["3 0 5 2"])
        self.assertNotIn("Game over: B", out)


class MultiCaptureTests(unittest.TestCase):
    def test_double_jump_keeps_turn_then_ends(self):
        b = make(R=[(6, 1)], B=[(5, 2), (3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3"])
        self.assertEqual(g.player, "R")              # still R's turn
        self.assertEqual(g.chain, (4, 3))
        self.assertEqual(g.board[5][2], ".")
        g, out = play(make(R=[(6, 1)], B=[(5, 2), (3, 4), (0, 1)]), "R",
                      ["6 1 4 3", "4 3 2 5"])
        self.assertEqual(g.board[5][2], ".")
        self.assertEqual(g.board[3][4], ".")
        self.assertEqual(g.board[2][5], "R")
        self.assertEqual(g.player, "B")
        self.assertIsNone(g.chain)

    def test_cannot_play_other_ordinary_move_mid_chain(self):
        b = make(R=[(6, 1), (7, 6)], B=[(5, 2), (3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3", "7 6 6 5"])
        self.assertIn("You must keep capturing with the piece at 4 3.", out)
        self.assertEqual(g.board[7][6], "R")
        self.assertEqual(g.player, "R")

    def test_cannot_switch_to_other_capturing_piece_mid_chain(self):
        b = make(R=[(6, 1), (4, 7)], B=[(5, 2), (3, 4), (3, 6), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3", "4 7 2 5"])
        self.assertIn("You must keep capturing", out)
        self.assertEqual(g.board[3][6], "B")         # untouched
        self.assertEqual(g.player, "R")

    def test_cannot_stop_chain_with_simple_step(self):
        b = make(R=[(6, 1)], B=[(5, 2), (3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3", "4 3 3 2"])
        self.assertIn("You must keep capturing", out)
        self.assertEqual(g.board[4][3], "R")

    def test_triple_zigzag_capture(self):
        b = make(R=[(7, 2)], B=[(6, 3), (4, 3), (2, 1), (0, 5)])
        g, out = play(b, "R", ["7 2 5 4", "5 4 3 2", "3 2 1 0"])
        for sq in [(6, 3), (4, 3), (2, 1)]:
            self.assertEqual(g.board[sq[0]][sq[1]], ".")
        self.assertEqual(g.board[1][0], "R")
        self.assertEqual(g.player, "B")

    def test_single_capture_ends_turn_when_no_followup(self):
        g, out = play(make(R=[(4, 5)], B=[(3, 4), (0, 1)]), "R", ["4 5 2 3"])
        self.assertEqual(g.player, "B")
        self.assertIsNone(g.chain)

    def test_chain_capturing_last_piece_ends_game(self):
        b = make(R=[(6, 1)], B=[(5, 2), (3, 4)])
        g, out = play(b, "R", ["6 1 4 3", "4 3 2 5"])
        self.assertIn("B has no pieces left. R wins!", out)

    def test_promotion_during_capture_ends_turn(self):
        # R man jumps into row 0 and is crowned; a backward jump would exist
        # for a king, but crowning ends the turn.
        b = make(R=[(2, 3)], B=[(1, 4), (1, 6)])
        g, out = play(b, "R", ["2 3 0 5"])
        self.assertEqual(g.board[0][5], "RK")
        self.assertEqual(g.board[1][6], "B")
        self.assertEqual(g.player, "B")
        self.assertIsNone(g.chain)


class KingTests(unittest.TestCase):
    def test_red_king_moves_both_directions(self):
        for end in ("3 2", "5 4", "3 4", "5 2"):
            b = make(RK=[(4, 3)], B=[(0, 1)])
            g, out = play(b, "R", [f"4 3 {end}"])
            er, ec = map(int, end.split())
            self.assertEqual(g.board[er][ec], "RK", end)
            self.assertEqual(g.player, "B", end)

    def test_black_king_moves_both_directions(self):
        for end in ("3 4", "5 2", "3 2", "5 4"):
            b = make(BK=[(4, 3)], R=[(7, 0)])
            g, out = play(b, "B", [f"4 3 {end}"])
            er, ec = map(int, end.split())
            self.assertEqual(g.board[er][ec], "BK", end)

    def test_regular_pieces_cannot_move_backward(self):
        g, out = play(make(R=[(4, 3)], B=[(0, 1)]), "R", ["4 3 5 4"])
        self.assertIn("Invalid move.", out)
        self.assertEqual(g.board[4][3], "R")
        g, out = play(make(B=[(4, 3)], R=[(7, 0)]), "B", ["4 3 3 4"])
        self.assertIn("Invalid move.", out)
        self.assertEqual(g.board[4][3], "B")

    def test_red_king_captures_backward(self):
        b = make(RK=[(4, 3)], B=[(5, 4), (0, 1)])
        g, out = play(b, "R", ["4 3 6 5"])
        self.assertEqual(g.board[5][4], ".")
        self.assertEqual(g.board[6][5], "RK")

    def test_red_king_captures_forward(self):
        b = make(RK=[(4, 3)], B=[(3, 4), (0, 1)])
        g, out = play(b, "R", ["4 3 2 5"])
        self.assertEqual(g.board[3][4], ".")
        self.assertEqual(g.board[2][5], "RK")

    def test_black_king_captures_both_directions(self):
        g, out = play(make(BK=[(4, 3)], R=[(3, 4), (7, 0)]), "B", ["4 3 2 5"])
        self.assertEqual((g.board[3][4], g.board[2][5]), (".", "BK"))
        g, out = play(make(BK=[(4, 3)], R=[(5, 2), (7, 0)]), "B", ["4 3 6 1"])
        self.assertEqual((g.board[5][2], g.board[6][1]), (".", "BK"))

    def test_king_multi_jump_changes_direction(self):
        b = make(RK=[(4, 3)], B=[(3, 4), (3, 6), (0, 1)])
        g, out = play(b, "R", ["4 3 2 5", "2 5 4 7"])   # forward then backward
        self.assertEqual(g.board[3][4], ".")
        self.assertEqual(g.board[3][6], ".")
        self.assertEqual(g.board[4][7], "RK")
        self.assertEqual(g.player, "B")

    def test_regular_piece_cannot_capture_backward(self):
        b = make(R=[(4, 3)], B=[(5, 4), (0, 1)])
        before = snapshot(b)
        g, out = play(b, "R", ["4 3 6 5"])
        self.assertIn("Invalid move.", out)
        self.assertEqual(g.board, before)

    def test_king_can_capture_enemy_king(self):
        g, out = play(make(R=[(4, 3)], BK=[(3, 2), (0, 1)]), "R", ["4 3 2 1"])
        self.assertEqual((g.board[3][2], g.board[2][1]), (".", "R"))

    def test_black_king_on_back_row_still_has_legal_moves(self):
        # Task 2 caveat: a BK on row 7 used to look permanently stuck.
        self.assertTrue(has_legal_move(make(BK=[(7, 0)]), "B"))


class PromotionTests(unittest.TestCase):
    def test_red_and_black_promote_on_correct_rows(self):
        b = make(R=[(1, 2), (5, 0)], B=[(6, 3)])
        g, out = play(b, "R", ["1 2 0 1", "6 3 7 2"])
        self.assertEqual(g.board[0][1], "RK")
        self.assertEqual(g.board[7][2], "BK")

    def test_no_promotion_on_other_rows(self):
        b = make(R=[(2, 3)], B=[(5, 2)])
        g, out = play(b, "R", ["2 3 1 2", "5 2 6 3"])
        self.assertEqual(g.board[1][2], "R")
        self.assertEqual(g.board[6][3], "B")

    def test_pieces_do_not_promote_on_their_own_start_side(self):
        b = make(B=[(0, 1)], R=[(7, 0)])
        promote(b)
        self.assertEqual((b[0][1], b[7][0]), ("B", "R"))

    def test_king_stays_single_king(self):
        b = make(RK=[(1, 2)], B=[(7, 6)])
        g, out = play(b, "R", ["1 2 0 1"])
        self.assertEqual(g.board[0][1], "RK")


class FriendlyPieceTests(unittest.TestCase):
    def test_man_cannot_jump_own_man(self):
        b = make(R=[(4, 3), (3, 2)], B=[(0, 1)])
        before = snapshot(b)
        g, out = play(b, "R", ["4 3 2 1"])
        self.assertIn("Invalid move.", out)
        self.assertEqual(g.board, before)
        self.assertEqual(g.player, "R")

    def test_man_cannot_jump_own_king(self):
        b = make(R=[(4, 3)], RK=[(3, 2)], B=[(0, 1)])
        before = snapshot(b)
        g, out = play(b, "R", ["4 3 2 1"])
        self.assertIn("Invalid move.", out)
        self.assertEqual(g.board, before)

    def test_black_cannot_jump_own_pieces(self):
        for friend in ("B", "BK"):
            b = make(B=[(3, 2)], R=[(7, 0)])
            b[4][3] = friend
            before = snapshot(b)
            g, out = play(b, "B", ["3 2 5 4"])
            self.assertEqual(g.board, before, friend)
            self.assertEqual(g.player, "B")

    def test_king_cannot_jump_own_piece(self):
        for friend in ("R", "RK"):
            b = make(RK=[(4, 3)], B=[(0, 1)])
            b[5][4] = friend
            before = snapshot(b)
            g, out = play(b, "R", ["4 3 6 5"])
            self.assertEqual(g.board, before, friend)

    def test_rules_level_ownership(self):
        b = make(R=[(4, 3)], RK=[(3, 2)])
        self.assertFalse(capture_move(b, "R", (4, 3), (2, 1)))
        b = make(R=[(4, 3)], BK=[(3, 2)])
        self.assertTrue(capture_move(b, "R", (4, 3), (2, 1)))
        b = make(R=[(4, 3)], B=[(3, 2)])
        self.assertTrue(capture_move(b, "R", (4, 3), (2, 1)))

    def test_friendly_piece_does_not_count_as_available_capture(self):
        # R has only the "jump" over its own king; that must not force a capture,
        # so an ordinary move is still allowed.
        b = make(R=[(4, 3), (6, 7)], RK=[(3, 2)], B=[(0, 1)])
        g, out = play(b, "R", ["6 7 5 6"])
        self.assertNotIn("mandatory", out)
        self.assertEqual(g.board[5][6], "R")


if __name__ == "__main__":
    unittest.main(verbosity=2)