# Space Invaders Game

This project is a terminal-based Space Invaders clone using **Pygame**. It introduces students to interactive game design using object-oriented principles and real-time graphical rendering.

---

## What’s Provided

A partially working version of a Space Invaders game with:

- A player-controlled ship that moves and shoots
- A grid of enemies that marches side to side and drops down at the edges
- Enemies that occasionally return fire
- Score display

You are expected to **analyze**, **interact with an AI assistant**, and **complete/fix** the game to make it fully functional.

### **Use an LLM (e.g. ChatGPT or Claude) as your debugging and pair-programming partner for this lab.**

---

## Getting Started

### Setup

1. Clone the repo or download the project folder.
2. Make sure you have Python 3.10+ installed.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the game:

```bash
python main.py
```

---

## Tasks to Complete

Each task must be completed using an iterative process involving LLM suggestions and your critical code review.

### Task 1: Refine Collision Detection

> Bullets sometimes pass straight through enemies without registering a hit, especially when firing rapidly or when two enemies are hit close together. Investigate and enhance collision accuracy.


### Task 2: Implement Game Over Condition

> Add a screen that displays the final score once the player is hit or the enemies reach the bottom of the screen, then gracefully waits for input instead of just printing to the console.



### Task 3: Add Replay Option

> After Game Over, allow the user to play again by choosing a difficulty (Easy, Medium, or Hard enemy speed/fire rate), or exit.



### Task 4: Add Sound Feedback

> Add basic sound effects for firing, an enemy being destroyed, and the game-over moment.


---

## Expected Behavior

- Smooth player movement using `Left`/`Right` or `A`/`D`, and shooting with `Space`
- Enemy grid marches side to side and drops down whenever it reaches a screen edge
- Enemies occasionally fire back at the player
- Score increases each time an enemy is destroyed
- Game ends when the player is hit by an enemy bullet or the enemy grid reaches the bottom of the screen

---

## Folder Structure

```
space-invaders-main/
├── main.py
├── requirements.txt
├── game/
│   ├── game_engine.py
│   ├── player.py
│   ├── enemy.py
│   └── bullet.py
└── README.md
```

---

## Submission Checklist

Submission is only the following three things:

- [] A 10-second video of gameplay **before** your changes, showing the bug/broken behavior
- [] A 10-second video of gameplay **after** your changes, showing the bug fixed and the new features working
- [] The Chat/LLM used page link, with the complete chat history
