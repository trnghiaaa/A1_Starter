# ============================================================================
# fly.py
# Purpose
#   Autonomous flocking agent with a small FSM.
#   States: Flock, Fleeing, Idle.
#   Flock uses boids separation, cohesion, alignment.
#   Fleeing uses flee or the new evade behavior.
#   Idle uses a gentle wander to drift when far from danger.
# Update order
#   Compute state transitions from triggers, then apply the behavior for state.
# ============================================================================

import random
from enum import Enum, auto
import pygame
from pygame.math import Vector2 as V2
from settings import (
    WIDTH, HEIGHT, WHITE, YELLOW, PURPLE,
    FLY_RADIUS, FLY_SPEED, NEIGHBOR_RADIUS,
    SEP_WEIGHT, COH_WEIGHT, ALI_WEIGHT, ANCHOR_WEIGHT
)
from utils import limit
from steering import (
    boids_separation, boids_cohesion, boids_alignment,
    flee, evade, wander_force
)

class FlyState(Enum):
    Flock   = auto()
    Fleeing = auto()
    Idle    = auto()

class Fly:
    def __init__(self, pos):
        self.pos = V2(pos)
        self.vel = V2(random.uniform(-1, 1), random.uniform(-1, 1))
        if self.vel.length_squared() == 0:
            self.vel = V2(1, 0)
        self.vel.scale_to_length(FLY_SPEED * 0.5)

        self.radius = FLY_RADIUS
        self.state = FlyState.Flock

        # Timers and cached values
        self.scare_timer = 0.0   # counts down while nervous before calming
        self.idle_timer  = 0.0   # time spent far from frog
        self._rng_seed   = random.randint(0, 999999)

        # Debug visualization attributes
        self.last_steer  = V2()

    def sense_bubbles_close(self, bubbles, r):
        """Return True if any bubble is within range r of the fly."""
        for b in bubbles:
            if (b.pos - self.pos).length_squared() <= r * r:
                return True
        return False

    def update(self, dt, flies, frog, bounds_rect, bubbles):
        """
        Update FSM and behavior. Flies use perception to switch states.
        Parameters
          flies: list of all flies for neighborhood queries
          frog:  player agent used as a threat source
          bounds_rect: world rectangle for anchor force and containment
          bubbles: list of active bubbles to trigger panic
        """

        # Perception radii and timers for the FSM
        BubbleFleeRange = 140.0      # panic if bubble comes within this range
        StopFleeingRange = 220.0     # calm down when both frog and bubbles are beyond this
        IdleDistance = 380.0         # far enough to consider idling
        IdleDelay    = 2.0           # seconds of safety before entering Idle

        # Triggers based on the frog and bubbles
        dist_to_frog = (frog.pos - self.pos).length()
        scared_by_frog   = dist_to_frog < 160.0
        scared_by_bubble = self.sense_bubbles_close(bubbles, BubbleFleeRange)

        # ---------------- FSM transitions ----------------
        if self.state == FlyState.Flock:
            if scared_by_frog or scared_by_bubble:
                self.state = FlyState.Fleeing
                self.scare_timer = 0.6
            else:
                # Build idle time only when calm and far
                if dist_to_frog > IdleDistance:
                    self.idle_timer += dt
                    if self.idle_timer >= IdleDelay:
                        self.state = FlyState.Idle
                else:
                    self.idle_timer = 0.0

        elif self.state == FlyState.Fleeing:
            calm = dist_to_frog > StopFleeingRange and not self.sense_bubbles_close(bubbles, StopFleeingRange)
            if calm:
                self.scare_timer -= dt
                if self.scare_timer <= 0:
                    self.state = FlyState.Flock
                    self.idle_timer = 0.0
            else:
                self.scare_timer = 0.6

        elif self.state == FlyState.Idle:
            if scared_by_frog or scared_by_bubble:
                self.state = FlyState.Fleeing
                self.scare_timer = 0.6
            elif dist_to_frog <= IdleDistance:
                self.state = FlyState.Flock
                self.idle_timer = 0.0

        # ---------------- State behaviours ----------------
        if self.state == FlyState.Flock:
            # Build neighbor list for boids
            neighbors = []
            for f in flies:
                if f is self:
                    continue
                if (f.pos - self.pos).length_squared() <= NEIGHBOR_RADIUS ** 2:
                    neighbors.append((f.pos, f.vel))

            # Compute boids forces: separation, cohesion, alignment
            sep = boids_separation(self.pos, neighbors, sep_radius=50.0)
            coh = boids_cohesion(self.pos, neighbors)
            ali = boids_alignment(self.vel, neighbors)
            force = sep * SEP_WEIGHT + coh * COH_WEIGHT + ali * ALI_WEIGHT

            # Gentle anchor toward arena center to avoid drifting out of bounds
            center = V2(bounds_rect.centerx, bounds_rect.centery)
            force += (center - self.pos) * ANCHOR_WEIGHT * 0.002

            # Integrate velocity
            self.vel += limit(force, 240.0) * dt

        elif self.state == FlyState.Fleeing:
            # Replace simple flee with predictive evade for extra credit
            force = evade(self.pos, self.vel, frog.pos, frog.vel, FLY_SPEED)

            # Anchor blend so the group does not disappear off screen
            center = V2(bounds_rect.centerx, bounds_rect.centery)
            force += (center - self.pos) * ANCHOR_WEIGHT * 0.002

            self.vel += limit(force, 340.0) * dt

        elif self.state == FlyState.Idle:
            # Use wander_force to provide gentle drifting
            force = wander_force(self.vel, rng_seed=self._rng_seed)
            self.vel += limit(force, 120.0) * dt
            self.vel *= 0.98  # mild damping so idle feels soft

        self.last_steer = V2(force)

        # Speed clamp and position integrate
        if self.vel.length() > FLY_SPEED:
            self.vel.scale_to_length(FLY_SPEED)
        self.pos += self.vel * dt

        # Soft containment inside arena
        if self.pos.x < self.radius:
            self.pos.x = self.radius; self.vel.x *= -0.4
        if self.pos.x > WIDTH - self.radius:
            self.pos.x = WIDTH - self.radius; self.vel.x *= -0.4
        if self.pos.y < self.radius:
            self.pos.y = self.radius; self.vel.y *= -0.4
        if self.pos.y > HEIGHT - self.radius:
            self.pos.y = HEIGHT - self.radius; self.vel.y *= -0.4

    def draw(self, surf):
        color = YELLOW if self.state in (FlyState.Flock, FlyState.Idle) else PURPLE
        pygame.draw.circle(surf, color, self.pos, self.radius)

    def draw_debug(self, surf, flies, font):
        """Render AI debug visualization overlay for this fly when debug_mode is ON."""
        # 1. Boids flocking connection lines to nearby neighbors within NEIGHBOR_RADIUS (120px)
        for f in flies:
            if f is not self:
                d2 = (f.pos - self.pos).length_squared()
                if d2 <= NEIGHBOR_RADIUS ** 2:
                    pygame.draw.line(surf, (100, 220, 255, 60), self.pos, f.pos, 1)

        # 2. Vectors (Velocity = BLUE, Steering = RED)
        if self.vel.length_squared() > 0:
            end_v = self.pos + self.vel * 0.35
            pygame.draw.line(surf, (80, 160, 255), self.pos, end_v, 2)
        if self.last_steer.length_squared() > 0:
            end_s = self.pos + self.last_steer * 0.35
            pygame.draw.line(surf, (255, 90, 90), self.pos, end_s, 2)

        # 3. State Text Label
        state_str = f"Fly: {self.state.name}"
        if self.state == FlyState.Idle and self.idle_timer > 0:
            state_str += f" ({self.idle_timer:.1f}s)"
        elif self.state == FlyState.Fleeing and self.scare_timer > 0:
            state_str += f" ({self.scare_timer:.1f}s)"
        txt = font.render(state_str, True, (255, 255, 180))
        surf.blit(txt, (int(self.pos.x - txt.get_width() // 2), int(self.pos.y - self.radius - 16)))
