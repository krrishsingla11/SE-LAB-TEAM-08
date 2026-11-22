import random

SIZE = 4


class Board:
    def __init__(self):
        self.grid = [[0] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.last_points_gained = 0
        self.add_random_tile()
        self.add_random_tile()

    def add_random_tile(self):
        empty = [(r, c) for r in range(SIZE) for c in range(SIZE) if self.grid[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            self.grid[r][c] = 4 if random.random() < 0.1 else 2

    @staticmethod
    def slide_line_with_score(line):
        """Slide and merge a single row/column according to 2048 rules.
        
        An original tile can participate in at most one merge per move.
        Returns (merged_line, points_gained).
        """
        values = [x for x in line if x != 0]
        result = []
        points = 0
        i = 0
        while i < len(values):
            if i + 1 < len(values) and values[i] == values[i + 1]:
                merged_value = values[i] * 2
                result.append(merged_value)
                points += merged_value
                i += 2
            else:
                result.append(values[i])
                i += 1
        result.extend([0] * (SIZE - len(result)))
        return result, points

    @staticmethod
    def slide_line(line):
        """Public static slide_line returning the slid line without score tuple."""
        result, _ = Board.slide_line_with_score(line)
        return result

    def move_left(self):
        changed = False
        step_points = 0
        for r in range(SIZE):
            old = self.grid[r][:]
            new_row, pts = self.slide_line_with_score(old)
            self.grid[r] = new_row
            step_points += pts
            if old != new_row:
                changed = True
        self.score += step_points
        self.last_points_gained = step_points
        return changed

    def move_right(self):
        changed = False
        step_points = 0
        for r in range(SIZE):
            old = self.grid[r][:]
            slid, pts = self.slide_line_with_score(list(reversed(old)))
            new_row = list(reversed(slid))
            self.grid[r] = new_row
            step_points += pts
            if old != new_row:
                changed = True
        self.score += step_points
        self.last_points_gained = step_points
        return changed

    def move_up(self):
        changed = False
        step_points = 0
        for c in range(SIZE):
            old = [self.grid[r][c] for r in range(SIZE)]
            slid, pts = self.slide_line_with_score(old)
            for r in range(SIZE):
                self.grid[r][c] = slid[r]
            step_points += pts
            if old != slid:
                changed = True
        self.score += step_points
        self.last_points_gained = step_points
        return changed

    def move_down(self):
        changed = False
        step_points = 0
        for c in range(SIZE):
            old = [self.grid[r][c] for r in range(SIZE)]
            slid, pts = self.slide_line_with_score(list(reversed(old)))
            new_col = list(reversed(slid))
            for r in range(SIZE):
                self.grid[r][c] = new_col[r]
            step_points += pts
            if old != new_col:
                changed = True
        self.score += step_points
        self.last_points_gained = step_points
        return changed

    def can_move(self):
        if any(0 in row for row in self.grid):
            return True
        for r in range(SIZE):
            for c in range(SIZE):
                if c + 1 < SIZE and self.grid[r][c] == self.grid[r][c + 1]:
                    return True
                if r + 1 < SIZE and self.grid[r][c] == self.grid[r + 1][c]:
                    return True
        return False
