import unittest, builtins, io, contextlib, re
from board import initial_board
from game import Checkers


def empty():
    return [["."] * 8 for _ in range(8)]


def make(**pieces):
    b = empty()
    for piece, squares in pieces.items():
        for r, c in squares:
            b[r][c] = piece
    return b


def play(board, player, moves):
    """Run from `board` (or the start position if None); 'q' is appended."""
    it = iter(moves + ["q"])
    builtins.input = lambda prompt="": next(it)
    g = Checkers()
    if board is not None:
        g.board, g.player = board, player
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        g.run()
    return g, buf.getvalue()


ACTION = re.compile(r"^(R|B|RK|BK) (moves|captures) ")


def actions(out):
    """The player-facing result lines (one per accepted move)."""
    return [l for l in out.splitlines() if ACTION.match(l)]


class OrdinaryMoveFeedback(unittest.TestCase):
    def test_ordinary_moves_each_report_once(self):
        g, out = play(None, "R", ["5 4 4 5", "2 3 3 4"])
        self.assertEqual(actions(out), [
            "R moves (5,4) -> (4,5).",
            "B moves (2,3) -> (3,4).",
        ])

    def test_king_move_names_the_king(self):
        g, out = play(make(RK=[(4, 3)], B=[(0, 1)]), "R", ["4 3 5 4"])
        self.assertEqual(actions(out), ["RK moves (4,3) -> (5,4)."])


class CaptureFeedback(unittest.TestCase):
    def test_capture_names_piece_and_coordinates(self):
        g, out = play(None, "R", ["5 4 4 5", "2 3 3 4", "4 5 2 3"])
        acts = actions(out)
        self.assertEqual(len(acts), 3)
        self.assertEqual(acts[2], "R captures B at (3,4): (4,5) -> (2,3).")

    def test_capturing_a_king_says_so(self):
        g, out = play(make(R=[(4, 3)], BK=[(3, 2), (0, 7)]), "R", ["4 3 2 1"])
        self.assertEqual(actions(out), ["R captures BK at (3,2): (4,3) -> (2,1)."])

    def test_king_captures_backward_message(self):
        g, out = play(make(RK=[(4, 3)], B=[(5, 4), (0, 1)]), "R", ["4 3 6 5"])
        self.assertEqual(actions(out), ["RK captures B at (5,4): (4,3) -> (6,5)."])

    def test_black_capture_message(self):
        g, out = play(make(B=[(3, 2)], R=[(4, 3), (7, 0)]), "B", ["3 2 5 4"])
        self.assertEqual(actions(out), ["B captures R at (4,3): (3,2) -> (5,4)."])


class PromotionFeedback(unittest.TestCase):
    def test_red_promotion_by_move(self):
        g, out = play(make(R=[(1, 2), (5, 0)], B=[(3, 6)]), "R", ["1 2 0 1"])
        self.assertEqual(actions(out),
                         ["R moves (1,2) -> (0,1). Promoted to king: RK at (0,1)."])

    def test_black_promotion_by_move(self):
        g, out = play(make(B=[(6, 3)], R=[(4, 5)]), "B", ["6 3 7 2"])
        self.assertEqual(actions(out),
                         ["B moves (6,3) -> (7,2). Promoted to king: BK at (7,2)."])

    def test_promotion_by_capture_is_one_line_and_ends_turn(self):
        g, out = play(make(R=[(2, 3)], B=[(1, 4), (1, 6)]), "R", ["2 3 0 5"])
        self.assertEqual(actions(out), [
            "R captures B at (1,4): (2,3) -> (0,5). Promoted to king: RK at (0,5)."])
        self.assertNotIn("Jump again", out)
        self.assertEqual(g.player, "B")

    def test_king_moving_to_back_row_is_not_re_promoted(self):
        g, out = play(make(RK=[(1, 2)], B=[(7, 6)]), "R", ["1 2 0 1"])
        self.assertEqual(actions(out), ["RK moves (1,2) -> (0,1)."])
        self.assertNotIn("Promoted", out)


class MultiCaptureFeedback(unittest.TestCase):
    def test_double_jump_gives_two_distinct_lines(self):
        b = make(R=[(6, 1)], B=[(5, 2), (3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3", "4 3 2 5"])
        self.assertEqual(actions(out), [
            "R captures B at (5,2): (6,1) -> (4,3). Jump again from (4,3).",
            "R captures B at (3,4): (4,3) -> (2,5).",
        ])

    def test_triple_jump_only_last_line_has_no_jump_again(self):
        b = make(R=[(7, 2)], B=[(6, 3), (4, 3), (2, 1), (0, 5)])
        g, out = play(b, "R", ["7 2 5 4", "5 4 3 2", "3 2 1 0"])
        acts = actions(out)
        self.assertEqual(len(acts), 3)
        self.assertTrue(acts[0].endswith("Jump again from (5,4)."))
        self.assertTrue(acts[1].endswith("Jump again from (3,2)."))
        self.assertEqual(acts[2], "R captures B at (2,1): (3,2) -> (1,0).")

    def test_rejected_mid_chain_move_adds_no_result_line(self):
        b = make(R=[(6, 1), (7, 6)], B=[(5, 2), (3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3", "7 6 6 5"])
        self.assertEqual(len(actions(out)), 1)
        self.assertIn("You must keep capturing", out)

    def test_every_jump_is_reported_exactly_once(self):
        b = make(R=[(6, 1)], B=[(5, 2), (3, 4), (0, 1)])
        g, out = play(b, "R", ["6 1 4 3", "4 3 2 5"])
        acts = actions(out)
        self.assertEqual(len(acts), len(set(acts)))   # no duplicates
        self.assertEqual(len(acts), 2)                # 2 accepted moves, 2 lines


class NoFeedbackWhenNotAccepted(unittest.TestCase):
    def test_rejections_and_bad_input_produce_no_result_line(self):
        b = make(R=[(4, 5), (6, 1)], B=[(3, 4), (0, 1)])
        bad = ["6 1 5 0",      # ordinary move while capture is mandatory
               "4 5 5 4",      # backward step by a man
               "0 1 1 2",      # not R's piece
               "a b c d", "1 2", "9 9 9 9"]
        g, out = play(b, "R", bad)
        self.assertEqual(actions(out), [])
        self.assertIn("Capture is mandatory.", out)
        self.assertIn("Invalid move.", out)
        self.assertIn("That is not your piece.", out)
        self.assertEqual(g.player, "R")

    def test_quit_produces_no_result_line(self):
        g, out = play(None, "R", [])
        self.assertEqual(actions(out), [])

    def test_accepted_move_never_also_prints_a_rejection(self):
        g, out = play(None, "R", ["5 4 4 5"])
        for text in ("Invalid move.", "Capture is mandatory.", "must keep capturing"):
            self.assertNotIn(text, out)


class GameOverInteraction(unittest.TestCase):
    def test_winning_capture_reports_once_before_game_over(self):
        b = make(R=[(4, 5)], B=[(3, 4)])
        it = iter(["4 5 2 3"])                       # no 'q': game must end itself
        builtins.input = lambda prompt="": next(it)
        g = Checkers(); g.board, g.player = b, "R"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.run()
        out = buf.getvalue()
        lines = out.rstrip().splitlines()
        self.assertEqual(actions(out), ["R captures B at (3,4): (4,5) -> (2,3)."])
        self.assertEqual(out.count("Game over"), 1)
        self.assertTrue(lines[-1].startswith("Game over"))
        self.assertLess(out.index("R captures"), out.index("Game over"))

    def test_final_jump_of_a_chain_then_game_over(self):
        b = make(R=[(6, 1)], B=[(5, 2), (3, 4)])
        g, out = play(b, "R", ["6 1 4 3", "4 3 2 5"])
        self.assertEqual(len(actions(out)), 2)
        self.assertIn("B has no pieces left. R wins!", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)