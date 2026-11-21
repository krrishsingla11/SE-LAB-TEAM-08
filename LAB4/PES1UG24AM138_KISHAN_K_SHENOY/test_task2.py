from board import Board
from game import Game


def test_task2_win_detection():
    """Verify reaching 2048 detects a win."""
    g = Game()
    g.board.grid = [
        [1024, 1024, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    g.move("a")
    assert any(2048 in row for row in g.board.grid)


def test_task2_no_move_detection():
    """Verify full board with no matching adjacent tiles cannot move."""
    b = Board()
    b.grid = [
        [2, 4, 2, 4],
        [4, 2, 4, 2],
        [2, 4, 2, 4],
        [4, 2, 4, 2]
    ]
    assert b.can_move() is False


def test_task2_full_board_with_move_available():
    """Verify full board with adjacent equal tiles can still move."""
    b = Board()
    b.grid = [
        [2, 2, 4, 8],
        [4, 8, 2, 4],
        [2, 4, 8, 2],
        [4, 2, 4, 8]
    ]
    assert b.can_move() is True


def test_task2_unchanged_move_does_not_spawn_tile():
    """A move leaving the board unchanged must not alter board or create a new tile."""
    g = Game()
    g.board.grid = [
        [2, 4, 8, 16],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    empty_before = sum(row.count(0) for row in g.board.grid)
    changed = g.move("w")  # Already at top, move up does nothing
    assert changed is False
    empty_after = sum(row.count(0) for row in g.board.grid)
    assert empty_before == empty_after
    assert g.board.grid[0] == [2, 4, 8, 16]
