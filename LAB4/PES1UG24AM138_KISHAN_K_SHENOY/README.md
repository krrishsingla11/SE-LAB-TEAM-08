# Scenario 14 — 2048

A terminal 2048 implementation with directional movement and tile merging.

## Student Details
- **Student Name**: Kishan K Shenoy
- **SRN**: PES1UG24AM138
- **Assigned Scenario**: Scenario 14 — 2048
- **Repository**: `SETAPESU26/14_2048`

## Provided files

- `main.py` — entry point.
- `game.py` — game loop, commands, and game state.
- `board.py` — grid movement and tile logic.
- `requirements.txt` — dependency declaration.

## Setup

```bash
python main.py
```

No external packages are required (optional `pytest` for running test suites).

## Before changing the code

Run the starter and deliberately construct repeated-tile rows if possible. Read the
board movement code and trace one complete move from input to tile creation.

## Task 1 — Correct merge semantics

Fix the merge algorithm so an original tile can participate in at most one merge
during a single move. Preserve normal compression and movement behaviour.

**Done when:** repeated patterns such as four equal tiles produce the standard 2048
result, not a chain merge of a newly created tile in the same move.

## Task 2 — Finish game-state handling

Implement win detection, no-move detection, and correct tile creation semantics.
A move that leaves the board unchanged must not create a new tile.

**Done when:** reaching 2048 ends the game, a full board with no legal moves ends the
game, and unchanged moves do not alter the board.

## Task 3 — Undo and best score

Add a one-level undo. Restoring a move must restore both board contents and score.
Track the best score for the current run.

**Done when:** one undo reverses exactly one successful move and does not create a tile.

## Task 4 — Move feedback

Add concise feedback for successful moves and merges. Do not trigger feedback merely
because internal board-scanning functions were called.

**Done when:** one accepted move produces one action-level result and invalid/unchanged
moves do not claim that a move occurred.

## Verification & Automated Tests

Comprehensive pytest suites are provided:
- `test_task1.py`: Tests merge semantics, four-equal patterns `[2, 2, 2, 2] -> [4, 4, 0, 0]`, non-chaining `[2, 2, 4, 0] -> [4, 4, 0, 0]`.
- `test_task2.py`: Tests win detection at 2048, full board no-move detection, and unchanged move tile creation prevention.
- `test_task3.py`: Tests one-level undo, restoring board & score, and best score tracking.
- `test_task4.py`: Tests action-level move and merge feedback messages.

Run tests:
```bash
pytest -v
```

## Folder structure

```text
PES1UG24AM138_KISHAN_K_SHENOY/
├── README.md
├── requirements.txt
├── main.py
├── game.py
├── board.py
├── links.txt
├── Chat_History.pdf
├── test_task1.py
├── test_task2.py
├── test_task3.py
└── test_task4.py
```
