# ============================================================================
# snake.py
# Purpose
#   Predator agent with a five-state FSM.
#   States: PatrolAway, PatrolHome, Aggro, Harmless, Confused.
#   Aggro chases the frog. Harmless returns home after pacification.
#   Confused wanders briefly after reaching home, then resumes patrol.
# Update order
#   Evaluate transitions first, then run the behavior for the active state.
# Drawing
#   Simple circle with a tiny eye that turns toward the current velocity.
# ============================================================================

from enum import Enum, auto
import math, random
import pygame
from pygame.math import Vector2 as V2
from settings import (
    WIDTH, HEIGHT, WHITE,
    SNAKE_RADIUS, SNAKE_SPEED, AGGRO_RANGE, DEAGGRO_RANGE,
    AVOID_LOOKAHEAD
)
from utils import circlecast_hits_any_rect, circle_rect_intersect, nearest_point_on_rect
from steering import arrive, seek, seek_with_avoid, integrate_velocity, pursue, wander_force

class SnakeState(Enum):
    PatrolAway = auto()
    PatrolHome = auto()
    Aggro      = auto()
    Harmless   = auto()
    Confused   = auto()

class Snake:
    def __init__(self, pos, patrol_point, rects):
        # Motion and shape
        self.pos = V2(pos)
        self.vel = V2(1, 0)
        self.radius = SNAKE_RADIUS
        self.speed = SNAKE_SPEED

        # Home base and patrol destination
        self.home = V2(pos)
        self.patrol_point = V2(patrol_point)

        # Initial state
        self.state = SnakeState.PatrolAway

        # Obstacles for avoidance
        self.rects = rects

        # Adjust home and patrol_point if they happen to spawn inside or too close to any obstacle
        for r in self.rects:
            # Adjust home
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
                # Sync pos with the updated home
                self.pos = V2(self.home)

            # Adjust patrol_point
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

        # Drawing hint for head direction
        self.heading_deg = 0.0

        # Color varies by state for quick visual debug
        self.color = (190, 130, 110)

        # Confused state timer
        self.confused_timer = 0.0

        # Position history for rendering slithering trailing body segments
        self.history = [V2(self.pos) for _ in range(60)]

        # RNG for wander if needed
        self._rng_seed = random.randint(0, 999999)

    def set_state(self, st):
        """Switch to a new FSM state."""
        if st == SnakeState.Harmless and self.state != SnakeState.Harmless:
            # Instantly redirect velocity toward home for a swift, responsive turn
            d = self.home - self.pos
            if d.length_squared() > 0:
                self.vel = d.normalize() * self.speed * 1.2
            # Reset history buffer for clean segment turning
            self.history = [V2(self.pos) for _ in range(60)]
        self.state = st

    def update(self, dt, frog):
        """
        Update state transitions based on distance to frog and timers.
        Then compute a steering force for the active state and integrate motion.
        """

        # Distance to frog for transitions
        dist = (frog.pos - self.pos).length()

        # Check if frog is hidden inside a box
        frog_hidden = False
        for r in self.rects:
            if r.collidepoint(frog.pos):
                frog_hidden = True
                break

        # ---------------- FSM transitions ----------------
        if self.state == SnakeState.Aggro:
            if dist > DEAGGRO_RANGE or frog_hidden:
                self.set_state(SnakeState.PatrolHome)

        elif self.state in (SnakeState.PatrolHome, SnakeState.PatrolAway):
            if dist < AGGRO_RANGE and not frog_hidden:
                self.set_state(SnakeState.Aggro)

        elif self.state == SnakeState.Harmless:
            # When harmless snake reaches home, enter Confused briefly then resume patrol
            if (self.home - self.pos).length() < 32:
                self.confused_timer = 1.5  # seconds of confusion
                self.set_state(SnakeState.Confused)

        elif self.state == SnakeState.Confused:
            self.confused_timer -= dt
            if self.confused_timer <= 0:
                self.set_state(SnakeState.PatrolAway)

        # ---------------- State behaviours ----------------
        if self.state == SnakeState.Aggro:
            self.color = (255, 150, 150)
            # Calculate predicted future target for pursue with capped prediction (max 0.6s)
            d = frog.pos - self.pos
            time_horizon = min(d.length() / (self.speed + 1e-5), 0.6)
            target = frog.pos + frog.vel * time_horizon
            base_steer = seek(self.pos, self.vel, target, self.speed)
        elif self.state == SnakeState.PatrolAway:
            self.color = (100, 180, 255)  # Distinct Light Blue
            target = self.patrol_point
            base_steer = arrive(self.pos, self.vel, self.patrol_point, self.speed)
            if (self.patrol_point - self.pos).length() < 24:
                self.set_state(SnakeState.PatrolHome)
        elif self.state == SnakeState.PatrolHome:
            self.color = (180, 220, 180)
            target = self.home
            base_steer = arrive(self.pos, self.vel, self.home, self.speed)
            if (self.home - self.pos).length() < 24:
                self.set_state(SnakeState.PatrolAway)
        elif self.state == SnakeState.Harmless:
            self.color = (210, 130, 255)  # Distinct Light Purple / Violet
            target = self.home
            base_steer = arrive(self.pos, self.vel, self.home, self.speed * 1.25)
        else:  # Confused
            self.color = (245, 210, 160)
            target = None
            # Use larger jitter and zero circle distance for an erratic, "confused" zig-zag walk
            steer = wander_force(self.vel, jitter_deg=45.0, circle_distance=0.0, circle_radius=50.0, rng_seed=self._rng_seed)

        if target is not None:
            # Check if straight corridor to the target is blocked
            d = target - self.pos
            reach = min(AVOID_LOOKAHEAD * 1.8, d.length())
            end_point = self.pos + d.normalize() * reach if d.length_squared() > 0 else self.pos
            if circlecast_hits_any_rect(self.pos, end_point, self.radius * 1.1, self.rects):
                # Corridor is blocked: use 100% of the seek_with_avoid steering force with a safety buffer
                steer = seek_with_avoid(self.pos, self.vel, target, self.speed, self.radius * 1.1, self.rects)
            else:
                # Corridor is clear: use the state's natural base steer (arrive or pursue)
                steer = base_steer

        # Integrate velocity and update position
        self.vel = integrate_velocity(self.vel, steer, dt, self.speed)
        self.pos += self.vel * dt

        # Resolve collisions with static obstacles (pop out instantly)
        from utils import nearest_point_on_rect
        for r in self.rects:
            np = nearest_point_on_rect(self.pos, r)
            diff = self.pos - np
            dist = diff.length()
            if dist < self.radius:
                if dist > 0:
                    overlap = self.radius - dist
                    self.pos += diff.normalize() * overlap
                    # Zero out velocity component pointing into the obstacle
                    normal = diff.normalize()
                    if self.vel.dot(normal) < 0:
                        self.vel -= self.vel.dot(normal) * normal
                else:
                    # Deep penetration: pop to nearest edge
                    d_left = self.pos.x - r.left
                    d_right = r.right - self.pos.x
                    d_top = self.pos.y - r.top
                    d_bottom = r.bottom - self.pos.y
                    min_d = min(d_left, d_right, d_top, d_bottom)
                    if min_d == d_left:
                        self.pos.x = r.left - self.radius
                    elif min_d == d_right:
                        self.pos.x = r.right + self.radius
                    elif min_d == d_top:
                        self.pos.y = r.top - self.radius
                    else:
                        self.pos.y = r.bottom + self.radius
                    self.vel = V2()

        # Smooth eye heading based on velocity
        spd = self.vel.length()
        if spd > 4:
            def lerp(a, b, t): return a + (b - a) * t
            self.heading_deg = lerp(self.heading_deg, math.degrees(math.atan2(self.vel.y, self.vel.x)), 0.15)

        # Keep inside arena
        if self.pos.x < self.radius: self.pos.x = self.radius
        if self.pos.x > WIDTH - self.radius: self.pos.x = WIDTH - self.radius
        if self.pos.y < self.radius: self.pos.y = self.radius
        if self.pos.y > HEIGHT - self.radius: self.pos.y = HEIGHT - self.radius

        # Record position history for rendering slithering body segments
        if not self.history or (self.pos - self.history[-1]).length() > 70:
            # Reset history on teleports
            self.history = [V2(self.pos) for _ in range(60)]
        elif (self.pos - self.history[-1]).length() >= 3.5:
            self.history.append(V2(self.pos))
            if len(self.history) > 60:
                self.history.pop(0)

    def draw(self, surf):
        # 1. Render trailing body segments (from tail to head)
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
            # Calculate shaded segment color
            factor = 0.75 + 0.25 * (1.0 - (i + 1) / (segment_count + 1))
            seg_color = (
                max(0, min(255, int(self.color[0] * factor))),
                max(0, min(255, int(self.color[1] * factor))),
                max(0, min(255, int(self.color[2] * factor)))
            )
            pygame.draw.circle(surf, seg_color, (int(seg_pos.x), int(seg_pos.y)), int(r))

        # 2. Render head
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), int(self.radius))

        # 3. Render dual eyes oriented along heading direction
        heading_rad = math.radians(self.heading_deg)
        forward = V2(math.cos(heading_rad), math.sin(heading_rad))
        right = V2(-forward.y, forward.x)

        eye_offset_fwd = self.radius * 0.50
        eye_offset_side = self.radius * 0.42

        left_eye = self.pos + forward * eye_offset_fwd + right * eye_offset_side
        right_eye = self.pos + forward * eye_offset_fwd - right * eye_offset_side

        for eye_pos in [left_eye, right_eye]:
            pygame.draw.circle(surf, (20, 20, 20), (int(eye_pos.x), int(eye_pos.y)), 3)
            pygame.draw.circle(surf, WHITE, (int(eye_pos.x), int(eye_pos.y)), 4, 1)
