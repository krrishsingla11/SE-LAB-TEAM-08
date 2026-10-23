import pygame

class Enemy:
    def __init__(self, x, y, width=40, height=30):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.alive = True

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)


class EnemyGrid:
    def __init__(self, screen_width, rows=4, cols=8, speed=1.5, drop_amount=20):
        self.screen_width = screen_width
        self.speed = speed
        self.drop_amount = drop_amount
        self.direction = 1  # 1 = moving right, -1 = moving left

        self.enemies = []
        spacing_x, spacing_y = 55, 45
        start_x, start_y = 40, 40
        for row in range(rows):
            for col in range(cols):
                x = start_x + col * spacing_x
                y = start_y + row * spacing_y
                self.enemies.append(Enemy(x, y))

    def alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def move(self):
        alive = self.alive_enemies()
        if not alive:
            return

        min_x = min(e.x for e in alive)
        max_x = max(e.x + e.width for e in alive)

        hit_edge = (self.direction == 1 and max_x + self.speed >= self.screen_width) or \
                   (self.direction == -1 and min_x - self.speed <= 0)

        if hit_edge:
            self.direction *= -1
            for e in alive:
                e.y += self.drop_amount
        else:
            for e in alive:
                e.x += self.speed * self.direction

    def reached_bottom(self, limit_y):
        return any(e.y + e.height >= limit_y for e in self.alive_enemies())
