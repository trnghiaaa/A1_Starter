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

import random, math
from enum import Enum, auto
import pygame
from pygame.math import Vector2 as V2
from settings import (
    WIDTH, HEIGHT, WHITE, YELLOW, PURPLE,
    FLY_RADIUS, FLY_SPEED, NEIGHBOR_RADIUS,
    SEP_WEIGHT, FLEE_SEP_WEIGHT, COH_WEIGHT, ALI_WEIGHT, ANCHOR_WEIGHT
)
from utils import limit
from steering import (
    boids_separation, boids_cohesion, boids_alignment,
    evade, wander_force
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

        # 3D Flocking depth layer scale
        self.depth_scale = random.uniform(0.85, 1.15)

        # Timers and cached values
        self.scare_timer = 0.0   # counts down while nervous before calming
        self.idle_timer  = 0.0   # time spent far from frog
        self._rng_seed   = random.randint(0, 999999)

        # Debug visualization attributes
        self.last_steer  = V2()

    def get_neighbors(self, flies, radius=NEIGHBOR_RADIUS):
        """Return list of (pos, vel) for all other flies within perception radius."""
        r_sq = radius * radius
        return [
            (other.pos, other.vel) for other in flies
            if other is not self and (other.pos - self.pos).length_squared() <= r_sq
        ]

    def sense_bubbles_close(self, bubbles, r):
        """Return True if any bubble is within range r of the fly."""
        for b in bubbles:
            if (b.pos - self.pos).length_squared() <= r * r:
                return True
        return False

    def trigger_swarm_alarm(self, flies, vfx=None):
        """Alert neighboring flies in the swarm within perception radius."""
        if vfx:
            vfx.add_swarm_alarm_pulse(self.pos, radius=110.0)
        alarm_sq = 110.0 * 110.0
        for other in flies:
            if other != self and other.state != FlyState.Fleeing:
                if (other.pos - self.pos).length_squared() <= alarm_sq:
                    other.state = FlyState.Fleeing
                    other.scare_timer = 0.6

    def update(self, dt, flies, frog, bounds_rect, bubbles, vfx=None):
        """
        Update FSM and behavior. Flies use perception to switch states.
        Parameters
          flies: list of all flies for neighborhood queries
          frog:  player agent used as a threat source
          bounds_rect: world rectangle for anchor force and containment
          bubbles: list of active bubbles to trigger panic
          vfx: optional VFXManager for visual effects
        """

        # Perception radii and timers for the FSM
        BubbleFleeRange = 140.0      # panic if bubble comes within this range
        StopFleeingRange = 220.0     # calm down when both frog and bubbles are beyond this
        IdleDistance = 380.0         # far enough to consider idling
        IdleDelay    = 3.0           # seconds of continuous calm needed before idling

        # Triggers based on the frog and bubbles
        dist_to_frog = (frog.pos - self.pos).length()
        scared_by_frog   = dist_to_frog < 160.0
        scared_by_bubble = self.sense_bubbles_close(bubbles, BubbleFleeRange)

        # ---------------- FSM transitions ----------------
        if self.state == FlyState.Flock:
            if scared_by_frog or scared_by_bubble:
                self.state = FlyState.Fleeing
                self.scare_timer = 0.6
                self.trigger_swarm_alarm(flies, vfx)
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
                self.trigger_swarm_alarm(flies, vfx)
            elif dist_to_frog <= IdleDistance:
                self.state = FlyState.Flock
                self.idle_timer = 0.0

        # ---------------- State behaviours ----------------
        force = V2()  # default zero force; overwritten by each state branch
        if self.state == FlyState.Flock:
            neighbors = self.get_neighbors(flies)

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
            # Predictive evade (Part 3B) replaces basic flee with prediction
            force = evade(self.pos, self.vel, frog.pos, frog.vel, FLY_SPEED)

            # Separation so panicked flies scatter apart instead of clumping, using FLEE_SEP_WEIGHT
            neighbors = self.get_neighbors(flies)
            force += boids_separation(self.pos, neighbors, sep_radius=50.0) * FLEE_SEP_WEIGHT

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

        # Spawn occasional hovering water ripple when fleeing fast
        if vfx and self.state == FlyState.Fleeing and random.random() < 0.04:
            vfx.add_water_ripple(self.pos, radius=4.0, max_radius=12.0, color=(200, 160, 255))

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
        r = int(self.radius * self.depth_scale)
        if r < 3: r = 3

        # 1. Ground drop shadow
        sh_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(sh_surf, (0, 0, 0, 45), (r + 2, r + 2), r)
        surf.blit(sh_surf, (int(self.pos.x - r + 2), int(self.pos.y - r + 3)))

        # 2. High-frequency fluttering wings
        wing_anim = math.sin(pygame.time.get_ticks() * 0.04 + self._rng_seed) * (r * 0.7)
        if self.vel.length_squared() > 0:
            side = V2(-self.vel.y, self.vel.x).normalize()
        else:
            side = V2(0, 1)

        w1_pos = self.pos + side * (r * 0.7) + V2(0, wing_anim)
        w2_pos = self.pos - side * (r * 0.7) - V2(0, wing_anim)

        w_surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(w_surf, (240, 245, 255, 170), (r + 1, r + 1), int(r * 0.6))
        surf.blit(w_surf, (int(w1_pos.x - r - 1), int(w1_pos.y - r - 1)))
        surf.blit(w_surf, (int(w2_pos.x - r - 1), int(w2_pos.y - r - 1)))

        # 3. Main fly body with depth-based color shade
        base_color = YELLOW if self.state in (FlyState.Flock, FlyState.Idle) else PURPLE
        shade_factor = 0.85 + (self.depth_scale - 0.85) * 0.5  # foreground flies slightly brighter
        color = (
            max(0, min(255, int(base_color[0] * shade_factor))),
            max(0, min(255, int(base_color[1] * shade_factor))),
            max(0, min(255, int(base_color[2] * shade_factor)))
        )
        pygame.draw.circle(surf, color, (int(self.pos.x), int(self.pos.y)), r)

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
