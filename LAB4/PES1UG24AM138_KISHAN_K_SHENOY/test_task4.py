from game import Game


def test_task4_move_and_merge_feedback():
    """Verify informative feedback is generated for successful moves with merges."""
    g = Game()
    g.board.grid = [
        [2, 2, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.move("a")
    assert "Moved left" in g.last_action_feedback
    assert "(+4 pts)" in g.last_action_feedback


def test_task4_move_without_merge_feedback():
    """Verify feedback for move without merge."""
    g = Game()
    g.board.grid = [
        [0, 2, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.move("a")
    assert "Moved left" in g.last_action_feedback
    assert "Merged" not in g.last_action_feedback


def test_task4_unchanged_move_feedback():
    """Verify feedback when a directional move produces no change."""
    g = Game()
    g.board.grid = [
        [2, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.move("a")
    assert "No tiles moved" in g.last_action_feedback
