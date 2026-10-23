# Scenario 21 — Checkers

A modular terminal checkers game with a board, movement rules, captures, and promotion support.

## Provided files

- `main.py` — entry point.
- `game.py` — turn flow and interaction.
- `board.py` — board representation and movement.
- `rules.py` — legal-move and promotion rules.
- `requirements.txt` — dependency declaration.

## Setup

```bash
python main.py
```

## Before changing the code

Play enough turns to understand ordinary moves and captures. Set up a capture position
and inspect the board before and after the move.

## Task 1 — Capture correctness

When a legal capture is made, remove the opponent piece that was jumped. Preserve the
moving piece and its destination.

**Done when:** captured pieces disappear and cannot be captured again.

## Task 2 — Win and no-move detection

Detect when one side has no pieces or no legal moves. End the game cleanly in either case.

## Task 3 — Complete checkers rules

Add forced-capture behaviour, multi-capture turns, and king movement in both directions.
Promotion must occur at the correct back row.

## Task 4 — Move-level feedback

Add concise move/capture/promotion feedback. One accepted move should produce one
player-facing action result, even if several internal legal-move checks occur.

## Required testing

Test ordinary moves, captures, multiple captures, forced captures, promotion, king
movement, no-move positions, invalid coordinates, and quitting.


## LLM usage

You may use an LLM during the lab. The goal is to use it as a coding assistant while
retaining responsibility for understanding and testing the result.

- Inspect the existing code before asking for changes.
- Ask for explanations when you do not understand a proposed change.
- Test generated code against the stated behaviour and edge cases.
- Keep your complete LLM chat history for submission.
- Do not replace the whole project with an unrelated implementation.
- Keep all state in memory; do not add CSV, JSON, SQLite, or other persistence.

## Submission checklist

- [ ] Task 1 completed and the original defect was reproduced and fixed.
- [ ] Tasks 2–4 completed and tested.
- [ ] Boundary and invalid-input cases tested.
- [ ] No unnecessary external dependencies added.
- [ ] No persistent storage added.
- [ ] Code remains understandable and modular.
- [ ] Complete LLM chat-history link included.

## Folder structure

```text
scenario-09-checkers/
├── README.md
├── requirements.txt
├── main.py
├── game.py
├── board.py
└── rules.py
```

## Submission Checklist

Submission is only the following three things:

- [ ] A 10-second video of gameplay **before** your changes, showing the bug/broken behavior
- [ ] A 10-second video of gameplay **after** your changes, showing the bug fixed and the new features working
- [ ] The Chat/LLM used page link, with the complete chat history
