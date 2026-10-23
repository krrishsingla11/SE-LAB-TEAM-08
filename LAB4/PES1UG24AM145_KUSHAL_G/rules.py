SIZE = 8


def _opponent(player):
    return "B" if player == "R" else "R"


def _forward(player):
    return -1 if player == "R" else 1


def _is_king(piece):
    return piece.endswith("K")


def simple_move(board, player, start, end):
    sr, sc = start
    er, ec = end
    if board[er][ec] != "." or abs(er - sr) != 1 or abs(ec - sc) != 1:
        return False
    # Kings may step in both directions; ordinary pieces only forward.
    return _is_king(board[sr][sc]) or er - sr == _forward(player)


def capture_move(board, player, start, end):
    sr, sc = start
    er, ec = end
    if board[er][ec] != "." or abs(er - sr) != 2 or abs(ec - sc) != 2:
        return False
    # Kings may jump in both directions; ordinary pieces only forward.
    if not _is_king(board[sr][sc]) and er - sr != 2 * _forward(player):
        return False
    mr, mc = (sr + er) // 2, (sc + ec) // 2
    enemy = _opponent(player)
    # Only an opponent piece (man or king) may be jumped, never a friendly one.
    return board[mr][mc] in (enemy, enemy + "K")


def has_capture(board, player, start):
    """True if the piece at `start` has at least one legal capture."""
    r, c = start
    for dr in (-2, 2):
        for dc in (-2, 2):
            er, ec = r + dr, c + dc
            if 0 <= er < SIZE and 0 <= ec < SIZE:
                if capture_move(board, player, start, (er, ec)):
                    return True
    return False


def player_has_capture(board, player):
    """True if any piece of `player` has a legal capture (captures are mandatory)."""
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] in (player, player + "K") and has_capture(board, player, (r, c)):
                return True
    return False


def has_legal_move(board, player):
    """True if `player` has at least one move that simple_move/capture_move accept."""
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] not in (player, player + "K"):
                continue
            for dr in (-2, -1, 1, 2):
                for dc in (-2, -1, 1, 2):
                    er, ec = r + dr, c + dc
                    if not (0 <= er < SIZE and 0 <= ec < SIZE):
                        continue
                    if (simple_move(board, player, (r, c), (er, ec)) or
                            capture_move(board, player, (r, c), (er, ec))):
                        return True
    return False


def promote(board):
    for c in range(SIZE):
        if board[0][c] == "R":
            board[0][c] = "RK"
        if board[SIZE - 1][c] == "B":
            board[SIZE - 1][c] = "BK"