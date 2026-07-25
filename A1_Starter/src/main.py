import sys, random, math
import pygame
from settings import *
from utils import draw_grid, circle_rect_intersect, has_line_of_sight, ray_screen_edge_intersection
from world import World
from entities.frog import Frog
from entities.fly import Fly
from entities.snake import Snake, SnakeState
from vfx import VFXManager

def draw_threat_indicators(surf, frog, snakes, obstacles):
    """
    Render tactical screen-edge warning chevrons pointing toward Aggro snakes
    that are currently off-screen or obscured behind obstacle rectangles.
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

                pulse_speed = 0.012 + max(0.0, (380 - dist) * 0.00004)
                t = pygame.time.get_ticks() * pulse_speed
                size = 11.0 + math.sin(t) * 3.5

                angle_rad = math.atan2(d_vec.y, d_vec.x)
                fwd = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))
                perp = pygame.math.Vector2(-fwd.y, fwd.x)

                p1 = edge_pos + fwd * size
                p2 = edge_pos - fwd * (size * 0.7) + perp * (size * 0.7)
                p3 = edge_pos - fwd * (size * 0.7) - perp * (size * 0.7)

                pygame.draw.polygon(surf, (255, 50, 50), [(int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), (int(p3.x), int(p3.y))])
                pygame.draw.polygon(surf, (255, 220, 220), [(int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), (int(p3.x), int(p3.y))], 1)

def create_vignette_surface(w, h):
    """Pre-render a radial vignette overlay surface for edge darkening and danger feedback."""
    v_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    max_rings = 48
    for i in range(max_rings):
        alpha = int(255 * (1.0 - (i / max_rings) ** 0.55))
        rect = pygame.Rect(i * 2, i * 2, w - i * 4, h - i * 4)
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(v_surf, (150, 15, 15, alpha), rect, 3, border_radius=16)
    return v_surf

def main():
    pygame.init()
    pygame.display.set_caption("Frog, Flies, and Snakes")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 22)
    bigfont = pygame.font.SysFont("consolas", 48, bold=True)
    small_font = pygame.font.SysFont("consolas", 18, bold=True)

    vfx = VFXManager(font=small_font)
    render_surf = pygame.Surface((WIDTH, HEIGHT))
    vignette_surf = create_vignette_surface(WIDTH, HEIGHT)

    def reset():
        """Create a fresh world scene and entity instances."""
        world = World(WIDTH, HEIGHT)
        frog = Frog((WIDTH * 0.5, HEIGHT * 0.5))

        flies = [Fly((random.randint(60, WIDTH - 60), random.randint(60, HEIGHT - 60)))
                 for _ in range(NUM_FLIES)]

        snakes = []
        for i in range(NUM_SNAKES):
            px = 180 + i * 280
            py = 170 if i % 2 == 0 else HEIGHT - 170
            patrol = (WIDTH - px, HEIGHT - py)
            snakes.append(Snake((px, py), patrol, world.obstacles))

        return world, frog, flies, snakes

    world, frog, flies, snakes = reset()

    health = START_HEALTH
    fly_count = 0
    game_over = False
    win = False
    debug_mode = False
    paused = False
    elapsed_time = 0.0
    best_time = None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False

                if e.key == pygame.K_v:
                    debug_mode = not debug_mode

                if e.key == pygame.K_p:
                    paused = not paused

                if not game_over and not paused and e.key == pygame.K_SPACE:
                    frog.shoot()

                if (game_over or paused) and e.key == pygame.K_r:
                    world, frog, flies, snakes = reset()
                    health = START_HEALTH
                    fly_count = 0
                    game_over = False
                    win = False
                    paused = False
                    elapsed_time = 0.0
                    vfx.reset_combo()

            if not game_over and not paused and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                frog.set_target(pygame.mouse.get_pos())

        if not paused:
            vfx.update(dt)

        if not game_over and not paused:
            elapsed_time += dt

            frog.update(dt, vfx)

            current_time = pygame.time.get_ticks() / 1000.0
            eaten = []
            for f in flies:
                f.update(dt, flies, frog, world.rect, frog.bubbles, vfx)

                if (f.pos - frog.pos).length_squared() <= (f.radius + FROG_RADIUS) ** 2:
                    vfx.add_eat_fly(f.pos, current_time=current_time)
                    f.trigger_swarm_alarm(flies, vfx)
                    eaten.append(f)
                    fly_count += 1
                    if fly_count >= FLIES_TO_WIN:
                        game_over = True
                        win = True
                        if best_time is None or elapsed_time < best_time:
                            best_time = elapsed_time
            for f in eaten:
                flies.remove(f)

            for s in snakes:
                s.update(dt, frog, vfx)

            # Bubble collision logic
            for s in snakes:
                for b in frog.bubbles:
                    if b.alive and (b.pos - s.pos).length_squared() <= (BUBBLE_RADIUS + s.radius) ** 2:
                        if s.state == SnakeState.Aggro:
                            s.set_state(SnakeState.Harmless)
                        vfx.add_bubble_pop(b.pos)
                        b.alive = False

            for b in frog.bubbles:
                if b.alive:
                    for r in world.obstacles:
                        if circle_rect_intersect(b.pos, BUBBLE_RADIUS, r):
                            vfx.add_bubble_pop(b.pos)
                            b.alive = False
                            break

            # Player damage logic
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

        # Rendering pass
        render_surf.fill(BG)
        draw_grid(render_surf)
        world.draw(render_surf)

        frog.draw_target_marker(render_surf)

        for f in flies:
            f.draw(render_surf)
        for s in snakes:
            s.draw(render_surf)
        frog.draw(render_surf)
        vfx.draw(render_surf)

        draw_threat_indicators(render_surf, frog, snakes, world.obstacles)

        # Danger vignette screen tint
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

        # Debug visualization pass
        if debug_mode:
            frog.draw_debug(render_surf, small_font)
            for f in flies:
                f.draw_debug(render_surf, flies, small_font)
            for s in snakes:
                s.draw_debug(render_surf, small_font)

            dbg_badge = small_font.render("[DEBUG MODE: ON (V)]", True, (60, 240, 120))
            render_surf.blit(dbg_badge, (WIDTH - dbg_badge.get_width() - 16, 16))

        # Health UI
        for i in range(START_HEALTH):
            cx = 16 + i * 26
            cy = 18
            col = RED if i < health else (80, 60, 60)
            pygame.draw.circle(render_surf, col, (cx, cy), 10)
            pygame.draw.circle(render_surf, col, (cx + 12, cy), 10)
            points = [(cx - 6, cy + 2), (cx + 18, cy + 2), (cx + 6, cy + 18)]
            pygame.draw.polygon(render_surf, col, points)

        # Fly count UI and controls
        txt = font.render(f"Flies: {fly_count}/{FLIES_TO_WIN}", True, (240, 240, 240))
        render_surf.blit(txt, (16, 42))
        tips = font.render("Click: move | Space: bubble | P: Pause | V: Debug | R: restart", True, MUTED)
        render_surf.blit(tips, (16, 68))

        # Timer UI
        mins = int(elapsed_time // 60)
        secs = elapsed_time % 60
        timer_str = f"TIME: {mins:02d}:{secs:04.1f}s"
        timer_txt = font.render(timer_str, True, (240, 240, 240))
        render_surf.blit(timer_txt, (WIDTH // 2 - timer_txt.get_width() // 2, 16))

        if best_time is not None:
            bmins = int(best_time // 60)
            bsecs = best_time % 60
            best_str = f"BEST: {bmins:02d}:{bsecs:04.1f}s"
            best_txt = font.render(best_str, True, (255, 220, 90))
            render_surf.blit(best_txt, (WIDTH // 2 + timer_txt.get_width() // 2 + 20, 16))

        # Pause modal overlay
        if paused and not game_over:
            p_shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            p_shade.fill((0, 0, 0, 175))
            render_surf.blit(p_shade, (0, 0))

            card_w, card_h = 520, 310
            card_rect = pygame.Rect(WIDTH // 2 - card_w // 2, HEIGHT // 2 - card_h // 2, card_w, card_h)
            pygame.draw.rect(render_surf, (35, 42, 50), card_rect, border_radius=16)
            pygame.draw.rect(render_surf, (100, 200, 255), card_rect, 2, border_radius=16)

            title = bigfont.render("GAME PAUSED", True, (255, 230, 100))
            render_surf.blit(title, title.get_rect(center=(WIDTH // 2, card_rect.top + 45)))

            controls_info = [
                "• Left Click : Set Frog Move Target",
                "• Space Bar  : Shoot Bubble Projectile",
                "• Key 'P'    : Resume Gameplay",
                "• Key 'V'    : Toggle AI Debug Overlay",
                "• Key 'R'    : Restart Game",
            ]
            for idx, line_str in enumerate(controls_info):
                line_txt = small_font.render(line_str, True, (220, 230, 240))
                render_surf.blit(line_txt, (card_rect.left + 40, card_rect.top + 95 + idx * 28))

            resume_hint = font.render("Press P to resume", True, (100, 240, 160))
            render_surf.blit(resume_hint, resume_hint.get_rect(center=(WIDTH // 2, card_rect.bottom - 35)))

        # Game over screen
        if game_over:
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 160))
            render_surf.blit(shade, (0, 0))
            msg = "You won!" if win else "You died!"
            col = (90, 220, 120) if win else RED
            text = bigfont.render(msg, True, col)
            hint = font.render("Press R to restart", True, (240, 240, 240))
            rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
            render_surf.blit(text, rect)

            if win:
                win_time_str = f"Time: {mins:02d}:{secs:04.1f}s"
                if best_time is not None and elapsed_time <= best_time:
                    win_time_str += " (NEW BEST RECORD!)"
                time_sub = font.render(win_time_str, True, (255, 230, 100))
                render_surf.blit(time_sub, time_sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25)))
                render_surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 65)))
            else:
                render_surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 35)))

        # Screen shake output
        ox, oy = vfx.get_shake_offset()
        screen.fill((0, 0, 0))
        screen.blit(render_surf, (int(ox), int(oy)))
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
