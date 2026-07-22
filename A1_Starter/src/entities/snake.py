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
from utils import circlecast_hits_any_rect
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

        # Adjust home and patrol_point if they happen to spawn inside any obstacle
        from utils import nearest_point_on_rect
        for r in self.rects:
            # Adjust home
            if r.collidepoint(self.home):
                np = nearest_point_on_rect(self.home, r)
                diff = self.home - np
                if diff.length_squared() > 0:
                    self.home += diff.normalize() * (self.radius + 15)
                else:
                    d_left = self.home.x - r.left
                    d_right = r.right - self.home.x
                    d_top = self.home.y - r.top
                    d_bottom = r.bottom - self.home.y
                    min_d = min(d_left, d_right, d_top, d_bottom)
                    if min_d == d_left:
                        self.home.x = r.left - (self.radius + 15)
                    elif min_d == d_right:
                        self.home.x = r.right + (self.radius + 15)
                    elif min_d == d_top:
                        self.home.y = r.top - (self.radius + 15)
                    else:
                        self.home.y = r.bottom + (self.radius + 15)
                # Sync pos with the updated home
                self.pos = V2(self.home)

            # Adjust patrol_point
            if r.collidepoint(self.patrol_point):
                np = nearest_point_on_rect(self.patrol_point, r)
                diff = self.patrol_point - np
                if diff.length_squared() > 0:
                    self.patrol_point += diff.normalize() * (self.radius + 15)
                else:
                    d_left = self.patrol_point.x - r.left
                    d_right = r.right - self.patrol_point.x
                    d_top = self.patrol_point.y - r.top
                    d_bottom = r.bottom - self.patrol_point.y
                    min_d = min(d_left, d_right, d_top, d_bottom)
                    if min_d == d_left:
                        self.patrol_point.x = r.left - (self.radius + 15)
                    elif min_d == d_right:
                        self.patrol_point.x = r.right + (self.radius + 15)
                    elif min_d == d_top:
                        self.patrol_point.y = r.top - (self.radius + 15)
                    else:
                        self.patrol_point.y = r.bottom + (self.radius + 15)

        # Drawing hint for head direction
        self.heading_deg = 0.0

        # Color varies by state for quick visual debug
        self.color = (190, 130, 110)

        # Confused state timer
        self.confused_timer = 0.0

        # RNG for wander if needed
        self._rng_seed = random.randint(0, 999999)

    def set_state(self, st):
        """Switch to a new FSM state."""
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
            if (self.home - self.pos).length() < 12:
                self.confused_timer = 1.5  # seconds of confusion
                self.set_state(SnakeState.Confused)

        elif self.state == SnakeState.Confused:
            self.confused_timer -= dt
            if self.confused_timer <= 0:
                self.set_state(SnakeState.PatrolAway)

        # ---------------- State behaviours ----------------
        if self.state == SnakeState.Aggro:
            self.color = (255, 150, 150)
            # Calculate predicted future target for pursue
            d = frog.pos - self.pos
            time_horizon = d.length() / (self.speed + 1e-5)
            target = frog.pos + frog.vel * time_horizon
            base_steer = seek(self.pos, self.vel, target, self.speed)
        elif self.state == SnakeState.PatrolAway:
            self.color = (100, 180, 255)  # Distinct Light Blue
            target = self.patrol_point
            base_steer = arrive(self.pos, self.vel, self.patrol_point, self.speed)
            if (self.patrol_point - self.pos).length() < 10:
                self.set_state(SnakeState.PatrolHome)
        elif self.state == SnakeState.PatrolHome:
            self.color = (180, 220, 180)
            target = self.home
            base_steer = arrive(self.pos, self.vel, self.home, self.speed)
            if (self.home - self.pos).length() < 10:
                self.set_state(SnakeState.PatrolAway)
        elif self.state == SnakeState.Harmless:
            self.color = (210, 130, 255)  # Distinct Light Purple / Violet
            target = self.home
            base_steer = arrive(self.pos, self.vel, self.home, self.speed * 0.9)
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

    def draw(self, surf):
        # Body
        pygame.draw.circle(surf, self.color, self.pos, self.radius)
        # Simple eye in heading direction
        head = self.pos + V2(1, 0).rotate(self.heading_deg) * (self.radius - 2)
        pygame.draw.circle(surf, (30, 30, 30), head, 3)
        pygame.draw.circle(surf, WHITE, head, 5, 1)
