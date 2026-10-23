import os
import pygame
import random
from .player import Player
from .enemy import EnemyGrid
from .bullet import Bullet

# Game Engine

WHITE = (255, 255, 255)
GREEN = (0, 200, 0)
RED = (220, 60, 60)

# ---------------------------------------------------------------
# SETTINGS - change these to tune the game
# ---------------------------------------------------------------
# Must match the FPS used in main.py, because the fire chance is
# calculated per frame.
FPS = 60

# After game over, key presses are ignored for this long so a player who
# is still mashing keys doesn't skip the screen by accident.
# Set to 0 to accept keys immediately.
GAME_OVER_INPUT_DELAY_SECONDS = 0.75

# Difficulty settings - all in ONE place, easy to tweak.
#   enemy_speed              : pixels the enemy grid moves per frame
#   enemy_bullets_per_second : average bullets the WHOLE grid fires per second
# The order here is the order shown in the menu (keys 1, 2, 3).
DIFFICULTY_SETTINGS = {
    "Easy":   {"enemy_speed": 1.0, "enemy_bullets_per_second": 0.5},
    "Medium": {"enemy_speed": 1.5, "enemy_bullets_per_second": 1.0},
    "Hard":   {"enemy_speed": 2.5, "enemy_bullets_per_second": 2.0},
}
DEFAULT_DIFFICULTY = "Medium"

# Sound files (created by generate_sounds.py).
# The folder is found relative to THIS file, so it works no matter
# which folder you start the game from.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUND_DIR = os.path.join(PROJECT_DIR, "assets", "sounds")
SOUND_FILES = {
    "fire": "fire.wav",
    "explosion": "explosion.wav",
    "game_over": "game_over.wav",
}
SOUND_VOLUME = 0.5  # 0.0 (silent) to 1.0 (full)

# Game states
STATE_PLAYING = "playing"
STATE_GAME_OVER = "game_over"
STATE_MENU = "menu"

# Choices on the Game Over screen
GAME_OVER_OPTIONS = ["Play again", "Exit"]


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        # Fonts are created once: normal, big (titles), small (hints)
        self.font = pygame.font.SysFont("Arial", 30)
        self.title_font = pygame.font.SysFont("Arial", 64, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 24)

        # Names of the difficulties in menu order: ["Easy", "Medium", "Hard"]
        self.difficulty_names = list(DIFFICULTY_SETTINGS.keys())

        self.quit_requested = False  # main.py checks this to close the game

        # Load sounds once (they stay loaded for every replay).
        self.sounds = self._load_sounds()

        # Set up everything for the first game.
        self.start_new_game(DEFAULT_DIFFICULTY)

    # ------------------------------------------------------------
    # Sound
    # ------------------------------------------------------------
    def _load_sounds(self):
        """Load all sound effects. Returns a dict like {"fire": Sound or None}.
        If audio is not available, the game simply runs without sound."""
        sounds = {name: None for name in SOUND_FILES}

        # pygame.init() does not raise an error if there is no audio device,
        # so we make sure the mixer is really running here.
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
        except Exception as error:
            print("Audio not available, running without sound:", error)
            return sounds

        # Load each file separately, so one missing file doesn't
        # stop the others from loading.
        for name, filename in SOUND_FILES.items():
            path = os.path.join(SOUND_DIR, filename)
            try:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(SOUND_VOLUME)
                sounds[name] = sound
            except Exception as error:
                print(f"Could not load sound '{filename}' "
                      f"(run generate_sounds.py first?): {error}")
        return sounds

    def _play(self, name):
        """Play a sound by name. Does nothing if it didn't load."""
        sound = self.sounds.get(name)
        if sound is not None:
            try:
                sound.play()
            except Exception:
                pass  # a sound problem must never crash the game

    # ------------------------------------------------------------
    # New game / state changes
    # ------------------------------------------------------------
    def start_new_game(self, difficulty):
        """Reset EVERYTHING and start a fresh game on the given difficulty."""
        settings = DIFFICULTY_SETTINGS[difficulty]
        self.difficulty = difficulty

        # Fresh player and enemies (enemy speed comes from the difficulty)
        self.player = Player(self.width // 2 - 20, self.height - 50, 40, 20)
        self.enemy_grid = EnemyGrid(self.width, speed=settings["enemy_speed"])

        # Empty the bullets and reset the shooting cooldown
        self.player_bullets = []
        self.enemy_bullets = []
        self._shoot_cooldown = 0

        # Chance (per frame) that the enemy grid fires ONE bullet.
        # Example: 1.0 bullet/sec / 60 frames/sec = about 1.7% per frame.
        self.enemy_fire_chance = settings["enemy_bullets_per_second"] / FPS

        # Score and state
        self.score = 0
        self.state = STATE_PLAYING

        # Game Over screen state
        self._game_over_timer = 0   # frames since the game ended
        self._game_over_delay = int(GAME_OVER_INPUT_DELAY_SECONDS * FPS)
        self._game_over_selected = 0   # 0 = Play again, 1 = Exit

        # Menu state (highlight starts on the default difficulty)
        self._menu_selected = self.difficulty_names.index(DEFAULT_DIFFICULTY)

    def _end_game(self):
        """Switch to the Game Over screen (and play the game over sound ONCE)."""
        # Guard: if the game is already over (e.g. a bullet hit AND the
        # enemies reached the bottom in the same frame), do nothing, so
        # the sound is never played twice.
        if self.state == STATE_GAME_OVER:
            return

        self.state = STATE_GAME_OVER
        self._game_over_timer = 0
        self._game_over_selected = 0
        self._play("game_over")

    # ------------------------------------------------------------
    # Input
    # ------------------------------------------------------------
    def handle_event(self, event):
        # Only key presses matter here (window close is handled in main.py)
        if event.type != pygame.KEYDOWN:
            return

        if self.state == STATE_MENU:
            self._handle_menu_key(event.key)
        elif self.state == STATE_GAME_OVER:
            self._handle_game_over_key(event.key)
        else:
            # Playing: Space shoots
            if event.key == pygame.K_SPACE and self._shoot_cooldown <= 0:
                bullet_x = self.player.center_x() - 2
                self.player_bullets.append(Bullet(bullet_x, self.player.y, direction=-1))
                self._shoot_cooldown = 15
                self._play("fire")

    def _handle_game_over_key(self, key):
        # Esc or Q always quits (even during the short input delay).
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.quit_requested = True
            return

        # Ignore other keys until the delay has passed.
        if self._game_over_timer < self._game_over_delay:
            return

        if key == pygame.K_UP:
            self._game_over_selected = (self._game_over_selected - 1) % len(GAME_OVER_OPTIONS)
        elif key == pygame.K_DOWN:
            self._game_over_selected = (self._game_over_selected + 1) % len(GAME_OVER_OPTIONS)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._game_over_selected == 0:
                self.state = STATE_MENU          # Play again -> difficulty menu
            else:
                self.quit_requested = True       # Exit

    def _handle_menu_key(self, key):
        # Esc or Q quits from the menu too.
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.quit_requested = True
            return

        # Keys 1, 2, 3 pick a difficulty straight away.
        # (pygame.K_1, K_2, K_3 are consecutive numbers.)
        number_index = key - pygame.K_1
        if 0 <= number_index < len(self.difficulty_names):
            self.start_new_game(self.difficulty_names[number_index])
            return

        # Up/Down moves the highlight, Enter confirms.
        if key == pygame.K_UP:
            self._menu_selected = (self._menu_selected - 1) % len(self.difficulty_names)
        elif key == pygame.K_DOWN:
            self._menu_selected = (self._menu_selected + 1) % len(self.difficulty_names)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.start_new_game(self.difficulty_names[self._menu_selected])

    def handle_input(self):
        if self.state != STATE_PLAYING:
            return  # the player can only move while playing

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player.move(-self.player.speed, self.width)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player.move(self.player.speed, self.width)

    # ------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------
    def update(self):
        if self.state == STATE_GAME_OVER:
            # The game logic is stopped, but we keep counting frames so
            # the input delay on the Game Over screen can finish.
            self._game_over_timer += 1
            return
        if self.state != STATE_PLAYING:
            return  # nothing to update in the menu

        if self._shoot_cooldown > 0:
            self._shoot_cooldown -= 1

        self.enemy_grid.move()

        # Enemy fire: roll ONCE per frame for the whole grid (not once per
        # enemy). If the roll succeeds, one random living enemy shoots.
        # This keeps the fire rate steady no matter how many enemies are left.
        alive = self.enemy_grid.alive_enemies()
        if alive and random.random() < self.enemy_fire_chance:
            shooter = random.choice(alive)
            bullet_x = shooter.x + shooter.width // 2
            self.enemy_bullets.append(Bullet(bullet_x, shooter.y + shooter.height, direction=1))

        # Move every bullet (each one remembers where it was last frame).
        for bullet in self.player_bullets:
            bullet.move()
        for bullet in self.enemy_bullets:
            bullet.move()

        # --- Player bullets vs enemies ---
        # We build a NEW list of bullets that survive instead of removing
        # items from the list we are looping over (that caused skipped checks).
        surviving_bullets = []
        for bullet in self.player_bullets:
            path = bullet.swept_rect()  # everything the bullet crossed this frame
            hit_enemy = None

            # alive_enemies() is called fresh for every bullet, so an enemy
            # killed by an earlier bullet this frame can't be hit again.
            for enemy in self.enemy_grid.alive_enemies():
                if path.colliderect(enemy.rect()):
                    # If the path touches more than one enemy, take the
                    # lowest one (largest y) - the bullet reached it first.
                    if hit_enemy is None or enemy.y > hit_enemy.y:
                        hit_enemy = enemy

            if hit_enemy is not None:
                hit_enemy.alive = False   # at most ONE enemy per bullet
                self.score += 1           # the bullet is used up (not kept)
                self._play("explosion")   # enemy destroyed sound
            else:
                surviving_bullets.append(bullet)
        self.player_bullets = surviving_bullets

        # --- GAME OVER condition 1: an enemy bullet hits the player ---
        # Same swept check, so a fast bullet can't skip over the player.
        for bullet in self.enemy_bullets:
            if bullet.swept_rect().colliderect(self.player.rect()):
                self._end_game()
                break

        # Remove off-screen bullets AFTER collisions, so a bullet that hit
        # something and left the screen on the same frame still counts.
        self.player_bullets = [b for b in self.player_bullets if not b.off_screen(self.height)]
        self.enemy_bullets = [b for b in self.enemy_bullets if not b.off_screen(self.height)]

        # --- GAME OVER condition 2: the enemies reach the player's row ---
        if self.enemy_grid.reached_bottom(self.player.y):
            self._end_game()

    # ------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------
    def render(self, screen):
        # The difficulty menu has its own screen (no game behind it).
        if self.state == STATE_MENU:
            self._draw_menu(screen)
            return

        # Draw the game as usual (when the game is over it stays frozen
        # on screen behind the Game Over overlay).
        pygame.draw.rect(screen, GREEN, self.player.rect())

        for enemy in self.enemy_grid.alive_enemies():
            pygame.draw.rect(screen, WHITE, enemy.rect())

        for bullet in self.player_bullets:
            pygame.draw.rect(screen, WHITE, bullet.rect())
        for bullet in self.enemy_bullets:
            pygame.draw.rect(screen, RED, bullet.rect())

        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        screen.blit(score_text, (10, 10))

        # Current difficulty, top right
        level_text = self.small_font.render(self.difficulty, True, WHITE)
        screen.blit(level_text, level_text.get_rect(topright=(self.width - 10, 14)))

        if self.state == STATE_GAME_OVER:
            self._draw_game_over(screen)

    def _draw_options(self, screen, labels, selected, first_y, gap):
        """Draw a centered list of options; the selected one is green with a box."""
        center_x = self.width // 2
        for i, label in enumerate(labels):
            is_selected = (i == selected)
            color = GREEN if is_selected else WHITE
            text = self.font.render(label, True, color)
            rect = text.get_rect(center=(center_x, first_y + i * gap))
            screen.blit(text, rect)
            if is_selected:
                pygame.draw.rect(screen, GREEN, rect.inflate(40, 16), 2)

    def _draw_game_over(self, screen):
        # Semi-transparent dark layer so the text is easy to read.
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # last number = transparency (0-255)
        screen.blit(overlay, (0, 0))

        center_x = self.width // 2
        center_y = self.height // 2

        # "GAME OVER" title
        title = self.title_font.render("GAME OVER", True, RED)
        screen.blit(title, title.get_rect(center=(center_x, center_y - 100)))

        # Final score
        final_score = self.font.render(f"Final Score: {self.score}", True, WHITE)
        screen.blit(final_score, final_score.get_rect(center=(center_x, center_y - 30)))

        # Options - only shown once key presses are being accepted
        if self._game_over_timer >= self._game_over_delay:
            self._draw_options(screen, GAME_OVER_OPTIONS, self._game_over_selected,
                               first_y=center_y + 40, gap=60)
            hint = self.small_font.render("Up/Down + Enter to choose  |  Esc / Q to exit", True, WHITE)
            screen.blit(hint, hint.get_rect(center=(center_x, center_y + 170)))

    def _draw_menu(self, screen):
        center_x = self.width // 2

        title = self.title_font.render("DIFFICULTY", True, GREEN)
        screen.blit(title, title.get_rect(center=(center_x, 180)))

        # "1. Easy", "2. Medium", "3. Hard"
        labels = [f"{i + 1}. {name}" for i, name in enumerate(self.difficulty_names)]
        self._draw_options(screen, labels, self._menu_selected, first_y=300, gap=70)

        hint = self.small_font.render("Press 1/2/3, or Up/Down + Enter  |  Esc / Q to exit", True, WHITE)
        screen.blit(hint, hint.get_rect(center=(center_x, 560)))