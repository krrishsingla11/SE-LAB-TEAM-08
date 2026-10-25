import pygame

class Bullet:
    def __init__(self, x, y, width=4, height=12, speed=8, direction=-1):
        self.x = x
        self.y = y
        # Where the bullet was on the previous frame. Used to build the
        # "swept" rectangle so fast bullets can't skip over a target.
        self.prev_y = y
        self.width = width
        self.height = height
        self.speed = speed
        self.direction = direction  # -1 = moving up (player bullet), 1 = moving down (enemy bullet)

    def move(self):
        # Remember the old position BEFORE moving.
        self.prev_y = self.y
        self.y += self.speed * self.direction

    def off_screen(self, screen_height):
        return self.y < 0 or self.y > screen_height

    def rect(self):
        # Where the bullet is right now (used for drawing).
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def swept_rect(self):
        # One rectangle covering everything the bullet passed through
        # between the previous frame and this frame (old spot + new spot).
        top = min(self.prev_y, self.y)
        total_height = abs(self.y - self.prev_y) + self.height
        return pygame.Rect(self.x, top, self.width, total_height)