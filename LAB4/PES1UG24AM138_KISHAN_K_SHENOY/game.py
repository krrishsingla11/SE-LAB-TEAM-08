from board import Board


class Game:
    def __init__(self):
        self.board = Board()
        self.best_score = self.board.score
        self.undo_state = None  # (grid_copy, score)
        self.last_action_feedback = ""

    def display(self):
        print("\n" + "+------+------+------+------+")
        for row in self.board.grid:
            print("|" + "|".join(f"{x:^6}" if x else f"{' ':^6}" for x in row) + "|")
            print("+------+------+------+------+")
        print(f"Score: {self.board.score}  Best: {self.best_score}")
        if self.last_action_feedback:
            print(self.last_action_feedback)
            self.last_action_feedback = ""

    def move(self, key):
        direction_names = {
            "a": "left",
            "d": "right",
            "w": "up",
            "s": "down"
        }
        moves = {
            "a": self.board.move_left,
            "d": self.board.move_right,
            "w": self.board.move_up,
            "s": self.board.move_down
        }
        if key not in moves:
            return False

        # Save previous state for one-level undo
        prev_grid = [row[:] for row in self.board.grid]
        prev_score = self.board.score

        changed = moves[key]()
        if changed:
            self.undo_state = (prev_grid, prev_score)
            self.board.add_random_tile()
            self.best_score = max(self.best_score, self.board.score)
            direction = direction_names[key]
            pts = self.board.last_points_gained
            if pts > 0:
                self.last_action_feedback = f"Moved {direction}. Merged tiles (+{pts} pts)."
            else:
                self.last_action_feedback = f"Moved {direction}."
            return True
        else:
            self.last_action_feedback = "No tiles moved in that direction."
            return False

    def undo(self):
        if self.undo_state is None:
            self.last_action_feedback = "No move to undo."
            return False
        prev_grid, prev_score = self.undo_state
        self.board.grid = [row[:] for row in prev_grid]
        self.board.score = prev_score
        self.undo_state = None
        self.last_action_feedback = "Move undone successfully."
        return True

    def run(self):
        print("2048 — W/A/S/D to move, U to undo, Q to quit.")
        while True:
            self.display()
            if any(cell >= 2048 for row in self.board.grid for cell in row):
                print("Congratulations! You reached 2048!")
                return
            if not self.board.can_move():
                print("Game Over: No legal moves remain.")
                return
            key = input("> ").strip().lower()
            if key == "q":
                print("Thanks for playing!")
                return
            if key == "u":
                self.undo()
                continue
            if key not in "wasd":
                print("Invalid command. Use W/A/S/D to move, U to undo, Q to quit.")
                continue
            self.move(key)
