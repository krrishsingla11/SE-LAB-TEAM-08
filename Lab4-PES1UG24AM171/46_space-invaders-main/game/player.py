import pygame

class Player:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = 6

    def move(self, dx, screen_width):
        self.x += dx
        self.x = max(0, min(self.x, screen_width - self.width))

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def center_x(self):
        return self.x + self.width // 2
