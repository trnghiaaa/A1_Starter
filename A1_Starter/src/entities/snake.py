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
    SNAKE_RADIUS, SNAKE_SPEED, AGGRO_RANGE, DEAGGRO_RANGE
)
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

        # ---------------- FSM transitions ----------------
        if self.state == SnakeState.Aggro:
            if dist > DEAGGRO_RANGE:
                self.set_state(SnakeState.PatrolHome)

        elif self.state in (SnakeState.PatrolHome, SnakeState.PatrolAway):
            if dist < AGGRO_RANGE:
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
            # TODO: replace seek with pursue for smarter interception
            # steer = pursue(self.pos, self.vel, frog.pos, frog.vel, self.speed)
            steer = seek(self.pos, self.vel, frog.pos, self.speed)
            # Light avoidance to reduce obstacle collisions while aggro
            steer += seek_with_avoid(self.pos, self.vel, frog.pos, self.speed, self.radius, self.rects) * 0.25

        elif self.state == SnakeState.PatrolAway:
            self.color = (180, 200, 255)
            steer = arrive(self.pos, self.vel, self.patrol_point, self.speed)
            if (self.patrol_point - self.pos).length() < 10:
                self.set_state(SnakeState.PatrolHome)
            steer += seek_with_avoid(self.pos, self.vel, self.patrol_point, self.speed, self.radius, self.rects) * 0.25

        elif self.state == SnakeState.PatrolHome:
            self.color = (180, 220, 180)
            steer = arrive(self.pos, self.vel, self.home, self.speed)
            if (self.home - self.pos).length() < 10:
                self.set_state(SnakeState.PatrolAway)
            steer += seek_with_avoid(self.pos, self.vel, self.home, self.speed, self.radius, self.rects) * 0.25

        elif self.state == SnakeState.Harmless:
            self.color = (190, 180, 255)
            steer = arrive(self.pos, self.vel, self.home, self.speed * 0.9)
            steer += seek_with_avoid(self.pos, self.vel, self.home, self.speed, self.radius, self.rects) * 0.25

        else:  # Confused
            self.color = (245, 210, 160)
            # TODO: use wander_force for a gentle random walk during confusion
            # steer = wander_force(self.vel, rng_seed=self._rng_seed)
            steer = V2()

        # Integrate velocity and update position
        self.vel = integrate_velocity(self.vel, steer, dt, self.speed)
        self.pos += self.vel * dt

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
