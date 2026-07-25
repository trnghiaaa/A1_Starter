from enum import Enum, auto
import math, random
import pygame
from pygame.math import Vector2 as V2
from settings import (
    WIDTH, HEIGHT, WHITE,
    SNAKE_RADIUS, SNAKE_SPEED, AGGRO_RANGE, DEAGGRO_RANGE,
    AVOID_LOOKAHEAD, GAP_MAX_WIDTH, GAP_MIN_WIDTH, GAP_APPROACH_RADIUS
)
from utils import circlecast_hits_any_rect, circle_rect_intersect, nearest_point_on_rect, has_line_of_sight, find_corridor_gaps
from steering import arrive, seek, seek_with_avoid, integrate_velocity, pursue, wander_force, seek_through_gap

class SnakeState(Enum):
    PatrolAway = auto()
    PatrolHome = auto()
    Aggro      = auto()
    Harmless   = auto()
    Confused   = auto()

class Snake:
    """Predator snake agent governed by an FSM, obstacle avoidance, and gap corridor navigation."""
    def __init__(self, pos, patrol_point, rects):
        self.pos = V2(pos)
        self.vel = V2(1, 0)
        self.radius = SNAKE_RADIUS
        self.speed = SNAKE_SPEED

        self.home = V2(pos)
        self.patrol_point = V2(patrol_point)
        self.state = SnakeState.PatrolAway
        self.rects = rects

        # Reposition home/patrol points if spawned inside obstacles
        for r in self.rects:
            if circle_rect_intersect(self.home, self.radius + 20, r):
                np = nearest_point_on_rect(self.home, r)
                diff = self.home - np
                if diff.length_squared() > 0:
                    self.home += diff.normalize() * (self.radius + 25)
                else:
                    d_left = self.home.x - r.left
                    d_right = r.right - self.home.x
                    d_top = self.home.y - r.top
                    d_bottom = r.bottom - self.home.y
                    min_d = min(d_left, d_right, d_top, d_bottom)
                    if min_d == d_left:
                        self.home.x = r.left - (self.radius + 25)
                    elif min_d == d_right:
                        self.home.x = r.right + (self.radius + 25)
                    elif min_d == d_top:
                        self.home.y = r.top - (self.radius + 25)
                    else:
                        self.home.y = r.bottom + (self.radius + 25)
                self.pos = V2(self.home)

            if circle_rect_intersect(self.patrol_point, self.radius + 20, r):
                np = nearest_point_on_rect(self.patrol_point, r)
                diff = self.patrol_point - np
                if diff.length_squared() > 0:
                    self.patrol_point += diff.normalize() * (self.radius + 25)
                else:
                    d_left = self.patrol_point.x - r.left
                    d_right = r.right - self.patrol_point.x
                    d_top = self.patrol_point.y - r.top
                    d_bottom = r.bottom - self.patrol_point.y
                    min_d = min(d_left, d_right, d_top, d_bottom)
                    if min_d == d_left:
                        self.patrol_point.x = r.left - (self.radius + 25)
                    elif min_d == d_right:
                        self.patrol_point.x = r.right + (self.radius + 25)
                    elif min_d == d_top:
                        self.patrol_point.y = r.top - (self.radius + 25)
                    else:
                        self.patrol_point.y = r.bottom + (self.radius + 25)

        self.heading_deg = 0.0
        self.color = (190, 130, 110)
        self.confused_timer = 0.0
        self.bounce_timer = 0.0

        self.tongue_timer = random.uniform(-1.8, 0.0)
        self.aggro_flash_timer = 0.0
        self.history = [V2(self.pos) for _ in range(60)]
        self.ripple_timer = 0.0
        self._rng_seed = random.randint(0, 999999)

        self.last_steer = V2()
        self.debug_rays = []
        self.debug_chosen_target = None
        self.debug_gap_target = None

    def set_state(self, st, vfx=None):
        """Switch to a new FSM state."""
        if st == SnakeState.Aggro and self.state != SnakeState.Aggro:
            self.aggro_flash_timer = 0.4
            if vfx:
                vfx.add_aggro_hiss(self.pos)

        if st == SnakeState.Harmless and self.state != SnakeState.Harmless:
            d = self.home - self.pos
            if d.length_squared() > 0:
                self.vel = d.normalize() * self.speed * 1.2
            self.history = [V2(self.pos) for _ in range(60)]
        self.state = st

    def update(self, dt, frog, vfx=None):
        """Update state transitions, steering forces, and position integration."""
        if self.bounce_timer > 0:
            self.bounce_timer -= dt

        if self.aggro_flash_timer > 0:
            self.aggro_flash_timer -= dt

        self.tongue_timer -= dt
        if self.tongue_timer <= -2.4:
            self.tongue_timer = 0.35

        dist = (frog.pos - self.pos).length()

        frog_hidden = False
        for r in self.rects:
            if r.collidepoint(frog.pos):
                frog_hidden = True
                break

        # FSM state transitions
        if self.state == SnakeState.Aggro:
            if dist > DEAGGRO_RANGE or frog_hidden:
                self.set_state(SnakeState.PatrolHome, vfx)

        elif self.state in (SnakeState.PatrolHome, SnakeState.PatrolAway):
            can_see_frog = has_line_of_sight(self.pos, frog.pos, self.rects)
            if dist < AGGRO_RANGE and not frog_hidden and can_see_frog:
                self.set_state(SnakeState.Aggro, vfx)

        elif self.state == SnakeState.Harmless:
            if (self.home - self.pos).length() < 48:
                self.confused_timer = 2.0
                self.set_state(SnakeState.Confused, vfx)

        elif self.state == SnakeState.Confused:
            self.confused_timer -= dt
            if self.confused_timer <= 0:
                self.set_state(SnakeState.PatrolAway, vfx)

        # State behaviors
        if self.state == SnakeState.Aggro:
            self.color = (255, 150, 150)
            d = frog.pos - self.pos
            time_horizon = min(d.length() / (self.speed + 1e-5), 0.6)
            target = frog.pos + frog.vel * time_horizon
            base_steer = pursue(self.pos, self.vel, frog.pos, frog.vel, self.speed)
        elif self.state == SnakeState.PatrolAway:
            self.color = (100, 180, 255)
            target = self.patrol_point
            base_steer = arrive(self.pos, self.vel, self.patrol_point, self.speed)
            if (self.patrol_point - self.pos).length() < 42:
                self.set_state(SnakeState.PatrolHome)
        elif self.state == SnakeState.PatrolHome:
            self.color = (180, 220, 180)
            target = self.home
            base_steer = arrive(self.pos, self.vel, self.home, self.speed)
            if (self.home - self.pos).length() < 42:
                self.set_state(SnakeState.PatrolAway)
        elif self.state == SnakeState.Harmless:
            self.color = (210, 130, 255)
            target = self.home
            base_steer = arrive(self.pos, self.vel, self.home, self.speed * 1.25)
        else:  # Confused
            self.color = (245, 210, 160)
            target = None
            steer = wander_force(self.vel, jitter_deg=75.0, circle_distance=0.0, circle_radius=70.0, rng_seed=self._rng_seed)

        self.debug_rays = []
        self.debug_chosen_target = None
        self.debug_gap_target = None

        if target is not None:
            d = target - self.pos
            reach = min(AVOID_LOOKAHEAD * 1.8, d.length())
            end_point = self.pos + d.normalize() * reach if d.length_squared() > 0 else self.pos
            if circlecast_hits_any_rect(self.pos, end_point, self.radius * 1.1, self.rects, ignore_start=True):
                gap_steer = None
                if self.state == SnakeState.Aggro:
                    gap_info = self._find_best_gap_toward(target)
                    if gap_info is not None:
                        gap_mid, gap_dir, gap_w = gap_info
                        self.debug_gap_target = gap_mid
                        gap_steer = seek_through_gap(
                            self.pos, self.vel, target, gap_mid,
                            self.speed, GAP_APPROACH_RADIUS
                        )

                if gap_steer is not None:
                    steer = gap_steer
                else:
                    debug_out = {}
                    steer = seek_with_avoid(self.pos, self.vel, target, self.speed, self.radius * 1.1, self.rects, debug_out=debug_out)
                    self.debug_rays = debug_out.get('rays', [])
                    self.debug_chosen_target = debug_out.get('chosen', None)
            else:
                steer = base_steer

        self.last_steer = V2(steer)

        self.vel = integrate_velocity(self.vel, steer, dt, self.speed)
        self.pos += self.vel * dt

        if vfx and self.vel.length_squared() > 1600:
            self.ripple_timer -= dt
            if self.ripple_timer <= 0:
                vfx.add_water_ripple(self.pos, radius=12.0, max_radius=26.0, color=(120, 190, 240))
                self.ripple_timer = 0.16

        # Obstacle collision resolution
        for r in self.rects:
            np = nearest_point_on_rect(self.pos, r)
            diff = self.pos - np
            dist = diff.length()
            if dist < self.radius:
                if dist > 0:
                    overlap = self.radius - dist
                    self.pos += diff.normalize() * overlap
                    normal = diff.normalize()
                    dot = self.vel.dot(normal)
                    if dot < 0:
                        self.vel -= 1.4 * dot * normal
                        self.bounce_timer = 0.35
                        if vfx:
                            vfx.add_bounce_impact(self.pos, normal)
                else:
                    d_left = self.pos.x - r.left
                    d_right = r.right - self.pos.x
                    d_top = self.pos.y - r.top
                    d_bottom = r.bottom - self.pos.y
                    min_d = min(d_left, d_right, d_top, d_bottom)
                    if min_d == d_left:
                        self.pos.x = r.left - self.radius
                        self.vel.x = -abs(self.vel.x) * 0.8
                    elif min_d == d_right:
                        self.pos.x = r.right + self.radius
                        self.vel.x = abs(self.vel.x) * 0.8
                    elif min_d == d_top:
                        self.pos.y = r.top - self.radius
                        self.vel.y = -abs(self.vel.y) * 0.8
                    else:
                        self.pos.y = r.bottom + self.radius
                        self.vel.y = abs(self.vel.y) * 0.8

        spd = self.vel.length()
        if spd > 4:
            def lerp_angle(a, b, t):
                diff = (b - a + 180) % 360 - 180
                return a + diff * t
            base_heading = math.degrees(math.atan2(self.vel.y, self.vel.x))
            if self.state == SnakeState.Confused:
                head_wiggle = math.sin(pygame.time.get_ticks() * 0.015) * 55.0
                self.heading_deg = lerp_angle(self.heading_deg, base_heading + head_wiggle, 0.25)
            else:
                self.heading_deg = lerp_angle(self.heading_deg, base_heading, 0.15)

        if self.pos.x < self.radius: self.pos.x = self.radius
        if self.pos.x > WIDTH - self.radius: self.pos.x = WIDTH - self.radius
        if self.pos.y < self.radius: self.pos.y = self.radius
        if self.pos.y > HEIGHT - self.radius: self.pos.y = HEIGHT - self.radius

        if not self.history or (self.pos - self.history[-1]).length() > 70:
            self.history = [V2(self.pos) for _ in range(60)]
        elif (self.pos - self.history[-1]).length() >= 3.5:
            self.history.append(V2(self.pos))
            if len(self.history) > 60:
                self.history.pop(0)

    def _find_best_gap_toward(self, target):
        """Scan for narrow corridors between obstacles that lead toward the target."""
        gaps = find_corridor_gaps(self.rects, GAP_MAX_WIDTH, GAP_MIN_WIDTH)
        best = None
        best_score = float('inf')

        to_target = target - self.pos
        dist_to_target = to_target.length()
        if dist_to_target < 1e-3:
            return None
        target_dir = to_target.normalize()

        for gap_mid, gap_dir, gap_w in gaps:
            to_gap = gap_mid - self.pos
            if to_gap.length_squared() < 1e-3:
                continue

            dot = to_gap.normalize().dot(target_dir)
            if dot < 0.0:
                continue

            dist_gap_to_target = (target - gap_mid).length()
            if dist_gap_to_target > dist_to_target + 50:
                continue

            if not has_line_of_sight(self.pos, gap_mid, self.rects):
                continue

            score = to_gap.length() + dist_gap_to_target
            if score < best_score:
                best_score = score
                best = (gap_mid, gap_dir, gap_w)

        return best

    def draw(self, surf):
        segment_count = 5
        segment_radii = [
            self.radius * 0.88,
            self.radius * 0.76,
            self.radius * 0.64,
            self.radius * 0.52,
            self.radius * 0.40,
        ]

        for i in range(segment_count - 1, -1, -1):
            idx = max(0, len(self.history) - 1 - (i + 1) * 7)
            seg_pos = self.history[idx]
            r = segment_radii[i]
            factor = 0.75 + 0.25 * (1.0 - (i + 1) / (segment_count + 1))
            seg_color = (
                max(0, min(255, int(self.color[0] * factor))),
                max(0, min(255, int(self.color[1] * factor))),
                max(0, min(255, int(self.color[2] * factor)))
            )
            pygame.draw.circle(surf, seg_color, (int(seg_pos.x), int(seg_pos.y)), int(r))

        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), int(self.radius))

        heading_rad = math.radians(self.heading_deg)
        forward = V2(math.cos(heading_rad), math.sin(heading_rad))
        right = V2(-forward.y, forward.x)

        if self.tongue_timer > 0 and self.state != SnakeState.Confused:
            stem_start = self.pos + forward * (self.radius + 1)
            stem_end = self.pos + forward * (self.radius + 12)
            fork_l = stem_end + forward * 4 + right * (-3.5)
            fork_r = stem_end + forward * 4 + right * 3.5

            tongue_col = (245, 50, 60)
            pygame.draw.line(surf, tongue_col, (int(stem_start.x), int(stem_start.y)), (int(stem_end.x), int(stem_end.y)), 2)
            pygame.draw.line(surf, tongue_col, (int(stem_end.x), int(stem_end.y)), (int(fork_l.x), int(fork_l.y)), 2)
            pygame.draw.line(surf, tongue_col, (int(stem_end.x), int(stem_end.y)), (int(fork_r.x), int(fork_r.y)), 2)

        eye_offset_fwd = self.radius * 0.50
        eye_offset_side = self.radius * 0.42

        left_eye = self.pos + forward * eye_offset_fwd + right * eye_offset_side
        right_eye = self.pos + forward * eye_offset_fwd - right * eye_offset_side

        pupil_col = (245, 40, 40) if self.state == SnakeState.Aggro else (20, 20, 20)
        ring_col = (255, 140, 80) if self.state == SnakeState.Aggro else WHITE

        for eye_pos in [left_eye, right_eye]:
            pygame.draw.circle(surf, pupil_col, (int(eye_pos.x), int(eye_pos.y)), 3)
            pygame.draw.circle(surf, ring_col, (int(eye_pos.x), int(eye_pos.y)), 4, 1)

        if self.aggro_flash_timer > 0:
            progress = max(0.0, min(1.0, self.aggro_flash_timer / 0.4))
            ring_r = int(self.radius + (1.0 - progress) * 26)
            alpha = int(240 * progress)
            flash_surf = pygame.Surface((ring_r * 2 + 6, ring_r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (255, 60, 60, alpha), (ring_r + 3, ring_r + 3), ring_r, 3)
            surf.blit(flash_surf, (int(self.pos.x - ring_r - 3), int(self.pos.y - ring_r - 3)))

        if self.state == SnakeState.Confused:
            t = pygame.time.get_ticks() * 0.007
            center_star = self.pos + V2(0, -self.radius - 14)
            for i in range(3):
                ang = t + i * (math.pi * 2 / 3)
                sx = center_star.x + math.cos(ang) * 14
                sy = center_star.y + math.sin(ang) * 5
                pygame.draw.circle(surf, (255, 230, 90), (int(sx), int(sy)), 3)
                pygame.draw.circle(surf, (200, 150, 20), (int(sx), int(sy)), 3, 1)

        if self.bounce_timer > 0:
            progress = max(0.0, min(1.0, self.bounce_timer / 0.35))
            ring_r = int(self.radius + (1.0 - progress) * 22)
            alpha = int(220 * progress)
            ring_surf = pygame.Surface((ring_r * 2 + 6, ring_r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, (160, 235, 255, alpha), (ring_r + 3, ring_r + 3), ring_r, 3)
            surf.blit(ring_surf, (int(self.pos.x - ring_r - 3), int(self.pos.y - ring_r - 3)))

    def draw_debug(self, surf, font):
        """Render debug overlay visualization for snake entity."""
        aggro_surf = pygame.Surface((int(AGGRO_RANGE * 2 + 4), int(AGGRO_RANGE * 2 + 4)), pygame.SRCALPHA)
        pygame.draw.circle(aggro_surf, (232, 88, 88, 55), (int(AGGRO_RANGE + 2), int(AGGRO_RANGE + 2)), int(AGGRO_RANGE), 1)
        surf.blit(aggro_surf, (int(self.pos.x - AGGRO_RANGE - 2), int(self.pos.y - AGGRO_RANGE - 2)))

        deaggro_surf = pygame.Surface((int(DEAGGRO_RANGE * 2 + 4), int(DEAGGRO_RANGE * 2 + 4)), pygame.SRCALPHA)
        pygame.draw.circle(deaggro_surf, (185, 120, 250, 45), (int(DEAGGRO_RANGE + 2), int(DEAGGRO_RANGE + 2)), int(DEAGGRO_RANGE), 1)
        surf.blit(deaggro_surf, (int(self.pos.x - DEAGGRO_RANGE - 2), int(self.pos.y - DEAGGRO_RANGE - 2)))

        pygame.draw.line(surf, (100, 200, 255, 140), self.pos, self.patrol_point, 1)
        pygame.draw.line(surf, (180, 230, 180, 140), self.pos, self.home, 1)
        hx, hy = int(self.home.x), int(self.home.y)
        pygame.draw.polygon(surf, (120, 240, 140), [(hx, hy - 6), (hx + 6, hy), (hx, hy + 6), (hx - 6, hy)])
        px, py = int(self.patrol_point.x), int(self.patrol_point.y)
        pygame.draw.polygon(surf, (100, 200, 255), [(px, py - 6), (px + 6, py), (px, py + 6), (px - 6, py)])

        for p0, p1, is_blocked in self.debug_rays:
            col = (255, 60, 60) if is_blocked else (60, 240, 100)
            pygame.draw.line(surf, col, (int(p0.x), int(p0.y)), (int(p1.x), int(p1.y)), 1)
        
        if self.debug_chosen_target is not None:
            pygame.draw.line(surf, (60, 255, 120), (int(self.pos.x), int(self.pos.y)), (int(self.debug_chosen_target.x), int(self.debug_chosen_target.y)), 2)
            pygame.draw.circle(surf, (60, 255, 120), (int(self.debug_chosen_target.x), int(self.debug_chosen_target.y)), 4)

        if self.debug_gap_target is not None:
            gx, gy = int(self.debug_gap_target.x), int(self.debug_gap_target.y)
            pygame.draw.polygon(surf, (255, 80, 220), [(gx, gy - 8), (gx + 8, gy), (gx, gy + 8), (gx - 8, gy)])
            pygame.draw.line(surf, (255, 80, 220), (int(self.pos.x), int(self.pos.y)), (gx, gy), 2)

        if self.vel.length_squared() > 0:
            end_v = self.pos + self.vel * 0.4
            pygame.draw.line(surf, (80, 160, 255), self.pos, end_v, 2)
        if self.last_steer.length_squared() > 0:
            end_s = self.pos + self.last_steer * 0.4
            pygame.draw.line(surf, (255, 90, 90), self.pos, end_s, 2)

        state_str = f"Snake: {self.state.name}"
        if self.state == SnakeState.Confused:
            state_str += f" ({self.confused_timer:.1f}s)"
        txt = font.render(state_str, True, (255, 255, 200))
        surf.blit(txt, (int(self.pos.x - txt.get_width() // 2), int(self.pos.y - self.radius - 22)))
