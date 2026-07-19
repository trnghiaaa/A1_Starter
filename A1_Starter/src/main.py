# ============================================================================
# main.py
# Purpose
#   Entry point and game loop. Handles input, updates agents, and draws frames.
# Mental model
#   Each frame: measure dt, process input, update world and agents, draw UI.
#   Agents do not draw themselves until update is finished for the frame.
# Controls
#   Left click sets a target for the frog. Space shoots a bubble. R restarts.
# ============================================================================

import sys, random
import pygame
from settings import *
from utils import draw_grid
from world import World
from entities.frog import Frog
from entities.fly import Fly
from entities.snake import Snake

def main():
    # Initialize Pygame and create a window and a clock
    pygame.init()
    pygame.display.set_caption("Frog, Flies, and Snakes")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Fonts for text and overlay
    font = pygame.font.SysFont("consolas", 22)
    bigfont = pygame.font.SysFont("consolas", 48, bold=True)

    def reset():
        """
        Create a fresh world and agents. Called at start and when the player restarts.
        Returns a tuple of (world, frog, flies, snakes).
        """
        world = World(WIDTH, HEIGHT)
        frog = Frog((WIDTH * 0.5, HEIGHT * 0.5))

        # Randomly scatter flies inside the world bounds
        flies = [Fly((random.randint(60, WIDTH - 60), random.randint(60, HEIGHT - 60)))
                 for _ in range(NUM_FLIES)]

        # Create snakes with patrol points mirrored across the screen
        snakes = []
        for i in range(NUM_SNAKES):
            px = 140 + i * 320
            py = 120 if i % 2 == 0 else HEIGHT - 140
            patrol = (WIDTH - px, HEIGHT - py)
            snakes.append(Snake((px, py), patrol, world.obstacles))

        return world, frog, flies, snakes

    # Build initial state
    world, frog, flies, snakes = reset()

    # Game state for health, scoring, and endings
    health = START_HEALTH
    fly_count = 0
    game_over = False
    win = False

    running = True
    while running:
        # ---------------- Measure dt ----------------
        # Convert milliseconds to seconds for frame rate independent movement
        dt = clock.tick(FPS) / 1000.0

        # ---------------- Input ----------------
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False

                if not game_over and e.key == pygame.K_SPACE:
                    # Space shoots a bubble from the frog mouth
                    frog.shoot()

                if game_over and e.key == pygame.K_r:
                    # R restarts the whole scene
                    world, frog, flies, snakes = reset()
                    health = START_HEALTH
                    fly_count = 0
                    game_over = False
                    win = False

            if not game_over and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Left click sets a new move target for the frog
                frog.set_target(pygame.mouse.get_pos())

        # ---------------- Update ----------------
        if not game_over:
            # Update frog first since other agents may query frog position
            frog.update(dt)

            # Update flies and check if any fly gets caught by the frog
            for f in list(flies):
                f.update(dt, flies, frog, world.rect, frog.bubbles)

                # Eat a fly when close enough to the frog center
                if (f.pos - frog.pos).length_squared() <= (f.radius + FROG_RADIUS) ** 2:
                    flies.remove(f)
                    fly_count += 1
                    if fly_count >= FLIES_TO_WIN:
                        game_over = True
                        win = True

            # Update snakes and their FSM decisions
            for s in snakes:
                s.update(dt, frog)

            # ------------- Bubble hit logic -------------
            # For each bubble and snake pair, if they overlap:
            #   - pop the bubble
            #   - if the snake is Aggro, switch it to Harmless or Confused
            # This logic is left as a student task to connect FSMs and mechanics.
            # for s in snakes:
            #     for b in frog.bubbles:
            #         if (b.pos - s.pos).length_squared() <= (BUBBLE_RADIUS + s.radius) ** 2:
            #             # if s.state == SnakeState.Aggro: s.set_state(SnakeState.Harmless)
            #             # optional: on going harmless to home, then Confused for a short time
            #             b.alive = False

            # ------------- Damage logic -------------
            # Only Aggro snakes should damage the frog.
            # Use frog.can_be_hurt() to avoid multiple hits in a row.
            # After a hit, reduce health and optionally pacify the snake.
            # for s in snakes:
            #     if s.state == SnakeState.Aggro and (s.pos - frog.pos).length_squared() <= (s.radius + FROG_RADIUS) ** 2:
            #         if frog.can_be_hurt():
            #             health -= 1
            #             frog.start_hurt()
            #             s.set_state(SnakeState.Harmless)
            #             if health <= 0:
            #                 game_over = True
            #                 win = False

        # ---------------- Draw ----------------
        screen.fill(BG)           # clear background
        draw_grid(screen)         # draw a soft grid
        world.draw(screen)        # draw obstacles

        for f in flies:           # draw flies
            f.draw(screen)
        for s in snakes:          # draw snakes
            s.draw(screen)
        frog.draw(screen)         # draw frog and bubbles

        # Draw hearts for health
        for i in range(START_HEALTH):
            cx = 16 + i * 26
            cy = 18
            col = RED if i < health else (80, 60, 60)
            pygame.draw.circle(screen, col, (cx, cy), 10)
        pygame.draw.circle(screen, col, (cx + 12, cy), 10)
        points = [(cx - 6, cy + 2), (cx + 18, cy + 2), (cx + 6, cy + 18)]
        pygame.draw.polygon(screen, col, points)

        # Draw fly counter and control hint
        txt = font.render(f"Flies: {fly_count}/{FLIES_TO_WIN}", True, (240, 240, 240))
        screen.blit(txt, (16, 42))
        tips = font.render("Click to move, Space to bubble, R to restart", True, MUTED)
        screen.blit(tips, (16, 68))

        # If game over, dim the screen and show a message
        if game_over:
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 160))
            screen.blit(shade, (0, 0))
            msg = "You won!" if win else "You died!"
            col = (90, 220, 120) if win else RED
            text = bigfont.render(msg, True, col)
            hint = font.render("Press R to restart", True, (240, 240, 240))
            rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))
            screen.blit(text, rect)
            screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 44)))

        # Present the frame
        pygame.display.flip()

    # Clean shutdown
    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
