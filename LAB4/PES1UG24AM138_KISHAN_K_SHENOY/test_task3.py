from game import Game


def test_task3_undo_reverses_move_and_restores_score():
    """Verify undo restores both board contents and score."""
    g = Game()
    g.board.grid = [
        [2, 2, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.board.score = 50
    initial_grid = [row[:] for row in g.board.grid]

    # Make move left
    g.move("a")
    assert g.board.score == 54  # 50 + 4

    # Perform undo
    success = g.undo()
    assert success is True
    assert g.board.grid == initial_grid
    assert g.board.score == 50


def test_task3_best_score_tracking():
    """Verify best score increases with progress and is preserved across undo."""
    g = Game()
    g.board.grid = [
        [2, 2, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.board.score = 100
    g.best_score = 100

    g.move("a")
    assert g.board.score == 104
    assert g.best_score == 104

    # Undo restores current score but retains best score
    g.undo()
    assert g.board.score == 100
    assert g.best_score == 104


def test_task3_consecutive_undo_prevented():
    """Verify one-level undo only reverses one move."""
    g = Game()
    g.board.grid = [
        [2, 2, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.move("a")
    assert g.undo() is True
    # Second consecutive undo should fail
    assert g.undo() is False
