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
from entities.snake import Snake, SnakeState

from vfx import VFXManager
from utils import has_line_of_sight, ray_screen_edge_intersection
import math

def draw_threat_indicators(surf, frog, snakes, obstacles):
    """
    Render tactical screen-edge warning chevrons pointing toward Aggro snakes
    that are currently off-screen or obscured behind tree obstacles.
    """
    for s in snakes:
        if s.state == SnakeState.Aggro:
            is_offscreen = (s.pos.x < 35 or s.pos.x > WIDTH - 35 or s.pos.y < 35 or s.pos.y > HEIGHT - 35)
            is_obscured = not has_line_of_sight(frog.pos, s.pos, obstacles)

            if is_offscreen or is_obscured:
                d_vec = s.pos - frog.pos
                dist = d_vec.length()
                if dist < 1e-3:
                    continue
                edge_pos = ray_screen_edge_intersection(frog.pos, d_vec, margin=24)

                # Pulse rate accelerates as snake gets closer
                pulse_speed = 0.012 + max(0.0, (380 - dist) * 0.00004)
                t = pygame.time.get_ticks() * pulse_speed
                size = 11.0 + math.sin(t) * 3.5

                angle_rad = math.atan2(d_vec.y, d_vec.x)
                fwd = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))
                perp = pygame.math.Vector2(-fwd.y, fwd.x)

                p1 = edge_pos + fwd * size
                p2 = edge_pos - fwd * (size * 0.7) + perp * (size * 0.7)
                p3 = edge_pos - fwd * (size * 0.7) - perp * (size * 0.7)

                # Render glowing red threat chevron arrow
                pygame.draw.polygon(surf, (255, 50, 50), [(int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), (int(p3.x), int(p3.y))])
                pygame.draw.polygon(surf, (255, 220, 220), [(int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), (int(p3.x), int(p3.y))], 1)

def create_vignette_surface(w, h):
    """Pre-render a smooth radial vignette overlay surface with dark red/black edges."""
    v_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    max_rings = 48
    for i in range(max_rings):
        alpha = int(255 * (1.0 - (i / max_rings) ** 0.55))
        rect = pygame.Rect(i * 2, i * 2, w - i * 4, h - i * 4)
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(v_surf, (150, 15, 15, alpha), rect, 3, border_radius=16)
    return v_surf

def main():
    # Initialize Pygame and create a window and a clock
    pygame.init()
    pygame.display.set_caption("Frog, Flies, and Snakes")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Fonts for text and overlay
    font = pygame.font.SysFont("consolas", 22)
    bigfont = pygame.font.SysFont("consolas", 48, bold=True)
    small_font = pygame.font.SysFont("consolas", 18, bold=True)

    # VFX Manager
    vfx = VFXManager(font=small_font)

    # Main render surface for screen shake
    render_surf = pygame.Surface((WIDTH, HEIGHT))

    # Pre-render vignette overlay surface
    vignette_surf = create_vignette_surface(WIDTH, HEIGHT)

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
            px = 180 + i * 280
            py = 170 if i % 2 == 0 else HEIGHT - 170
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
    debug_mode = False

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

                if e.key == pygame.K_v:
                    # Toggle AI debug visualization overlay
                    debug_mode = not debug_mode

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
                    vfx.reset_combo()

            if not game_over and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Left click sets a new move target for the frog
                frog.set_target(pygame.mouse.get_pos())

        # ---------------- Update ----------------
        vfx.update(dt)

        if not game_over:
            # Update frog first since other agents may query frog position
            frog.update(dt)

            # Update flies and check if any fly gets caught by the frog
            current_time = pygame.time.get_ticks() / 1000.0
            for f in list(flies):
                f.update(dt, flies, frog, world.rect, frog.bubbles)

                # Eat a fly when close enough to the frog center
                if (f.pos - frog.pos).length_squared() <= (f.radius + FROG_RADIUS) ** 2:
                    vfx.add_eat_fly(f.pos, current_time=current_time)
                    flies.remove(f)
                    fly_count += 1
                    if fly_count >= FLIES_TO_WIN:
                        game_over = True
                        win = True

            # Update snakes and their FSM decisions
            for s in snakes:
                s.update(dt, frog, vfx)

            # ------------- Bubble hit logic -------------
            # For each bubble and snake pair, if they overlap:
            #   - pop the bubble
            #   - if the snake is Aggro, switch it to Harmless or Confused
            for s in snakes:
                for b in frog.bubbles:
                    if b.alive and (b.pos - s.pos).length_squared() <= (BUBBLE_RADIUS + s.radius) ** 2:
                        if s.state == SnakeState.Aggro:
                            s.set_state(SnakeState.Harmless)
                        vfx.add_bubble_pop(b.pos)
                        b.alive = False

            # Check bubble collisions with static obstacles (boxes)
            from utils import circle_rect_intersect
            for b in frog.bubbles:
                if b.alive:
                    for r in world.obstacles:
                        if circle_rect_intersect(b.pos, BUBBLE_RADIUS, r):
                            vfx.add_bubble_pop(b.pos)
                            b.alive = False
                            break

            # ------------- Damage logic -------------
            # Only Aggro snakes should damage the frog.
            # Use frog.can_be_hurt() to avoid multiple hits in a row.
            # After a hit, reduce health and optionally pacify the snake.
            for s in snakes:
                if s.state == SnakeState.Aggro and (s.pos - frog.pos).length_squared() <= (s.radius + FROG_RADIUS) ** 2:
                    if frog.can_be_hurt():
                        health -= 1
                        frog.start_hurt()
                        vfx.add_hurt_impact(frog.pos)
                        s.set_state(SnakeState.Harmless)
                        if health <= 0:
                            game_over = True
                            win = False

        # ---------------- Draw ----------------
        render_surf.fill(BG)           # clear background
        draw_grid(render_surf)         # draw a soft grid
        world.draw(render_surf)        # draw obstacles

        # Tactical overlay (Target destination marker)
        frog.draw_target_marker(render_surf)

        for f in flies:                # draw flies
            f.draw(render_surf)
        for s in snakes:               # draw snakes
            s.draw(render_surf)
        frog.draw(render_surf)         # draw frog and bubbles
        vfx.draw(render_surf)          # draw particles and floating text

        # Tactical off-screen/obscured threat warning indicators
        draw_threat_indicators(render_surf, frog, snakes, world.obstacles)

        # Dynamic Vignette & Danger Screen Tint
        aggro_dists = [(s.pos - frog.pos).length() for s in snakes if s.state == SnakeState.Aggro]
        min_aggro_dist = min(aggro_dists) if aggro_dists else 9999.0

        vignette_alpha = 0
        if health == 1:
            vignette_alpha += int(55 + math.sin(pygame.time.get_ticks() * 0.006) * 30)
        if min_aggro_dist < 190.0:
            prox_ratio = (190.0 - min_aggro_dist) / 190.0
            vignette_alpha += int(prox_ratio * 165)
        vignette_alpha = min(210, max(0, vignette_alpha))

        if vignette_alpha > 0:
            vignette_surf.set_alpha(vignette_alpha)
            render_surf.blit(vignette_surf, (0, 0))

        # ---------------- AI Debug Visualization Overlay ----------------
        if debug_mode:
            frog.draw_debug(render_surf, small_font)
            for f in flies:
                f.draw_debug(render_surf, flies, small_font)
            for s in snakes:
                s.draw_debug(render_surf, small_font)

            # Debug status badge in top right
            dbg_badge = small_font.render("[DEBUG MODE: ON (V)]", True, (60, 240, 120))
            render_surf.blit(dbg_badge, (WIDTH - dbg_badge.get_width() - 16, 16))

        # Draw hearts for health
        for i in range(START_HEALTH):
            cx = 16 + i * 26
            cy = 18
            col = RED if i < health else (80, 60, 60)
            pygame.draw.circle(render_surf, col, (cx, cy), 10)
            pygame.draw.circle(render_surf, col, (cx + 12, cy), 10)
            points = [(cx - 6, cy + 2), (cx + 18, cy + 2), (cx + 6, cy + 18)]
            pygame.draw.polygon(render_surf, col, points)

        # Draw fly counter and control hint
        txt = font.render(f"Flies: {fly_count}/{FLIES_TO_WIN}", True, (240, 240, 240))
        render_surf.blit(txt, (16, 42))
        tips = font.render("Click: move | Space: bubble | V: Debug Mode | R: restart", True, MUTED)
        render_surf.blit(tips, (16, 68))

        # If game over, dim the screen and show a message
        if game_over:
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 160))
            render_surf.blit(shade, (0, 0))
            msg = "You won!" if win else "You died!"
            col = (90, 220, 120) if win else RED
            text = bigfont.render(msg, True, col)
            hint = font.render("Press R to restart", True, (240, 240, 240))
            rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))
            render_surf.blit(text, rect)
            render_surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 44)))

        # Present the frame with screen shake offset
        ox, oy = vfx.get_shake_offset()
        screen.fill((0, 0, 0))
        screen.blit(render_surf, (int(ox), int(oy)))
        pygame.display.flip()

    # Clean shutdown
    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
