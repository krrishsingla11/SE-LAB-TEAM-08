from board import Board


def test_task1_single_merge_per_tile():
    """Verify an original tile participates in at most one merge during a single move."""
    # [2, 2, 4, 0] must become [4, 4, 0, 0] and NOT chain into [8, 0, 0, 0]
    line = [2, 2, 4, 0]
    result = Board.slide_line(line)
    assert result == [4, 4, 0, 0]


def test_task1_four_equal_tiles():
    """Verify repeated patterns such as four equal tiles produce [4, 4, 0, 0]."""
    line = [2, 2, 2, 2]
    result = Board.slide_line(line)
    assert result == [4, 4, 0, 0]


def test_task1_three_equal_tiles():
    """Verify [4, 4, 4, 0] becomes [8, 4, 0, 0]."""
    line = [4, 4, 4, 0]
    result = Board.slide_line(line)
    assert result == [8, 4, 0, 0]


def test_task1_separated_equal_pairs():
    """Verify separated equals compress and merge correctly."""
    line = [2, 0, 2, 4]
    result = Board.slide_line(line)
    assert result == [4, 4, 0, 0]


def test_task1_score_accumulation():
    """Verify points are accumulated accurately on merge."""
    b = Board()
    b.grid = [
        [2, 2, 0, 0],
        [4, 4, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]
    b.score = 0
    b.move_left()
    # 2+2->4 (+4 pts), 4+4->8 (+8 pts), total +12 pts
    assert b.grid[0] == [4, 0, 0, 0]
    assert b.grid[1] == [8, 0, 0, 0]
    assert b.score == 12
    assert b.last_points_gained == 12
