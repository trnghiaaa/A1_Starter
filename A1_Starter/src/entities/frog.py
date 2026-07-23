# ============================================================================
# frog.py
# Purpose
#   Player controlled agent. Moves with Arrive. Shoots bubbles.
#   Holds a short Hurt state for temporary invulnerability after damage.
# Update order
#   Compute steering, integrate velocity with dt, clamp to bounds, update bubbles.
# Drawing
#   Draw the frog body and a simple eye that points in the facing direction.
# ============================================================================

# (no wall-clock imports needed — all timing uses dt)
import math
import pygame
from pygame.math import Vector2 as V2
from settings import (
    WIDTH, HEIGHT, WHITE, GREEN, BLUE,
    FROG_RADIUS, FROG_SPEED,
    BUBBLE_RADIUS, BUBBLE_SPEED, BUBBLE_LIFETIME,
    HURT_INVULN, ARRIVE_SLOW_RADIUS, ARRIVE_STOP_RADIUS
)
from utils import clamp
from steering import arrive, integrate_velocity

class Bubble:
    """
    Simple projectile that moves in a straight line and pops after a short time.
    You can destroy it early when it hits a snake or an obstacle.
    """
    def __init__(self, pos, dir_vec):
        self.pos = V2(pos)
        self.vel = (dir_vec.normalize() if dir_vec.length_squared() > 0 else V2(1, 0)) * BUBBLE_SPEED
        self.age = 0.0
        self.alive = True

    def update(self, dt):
        self.pos += self.vel * dt
        self.age += dt
        if self.age > BUBBLE_LIFETIME:
            self.alive = False

    def draw(self, surf):
        pygame.draw.circle(surf, BLUE, self.pos, BUBBLE_RADIUS)
        pygame.draw.circle(surf, WHITE, self.pos, BUBBLE_RADIUS, 2)

class Frog:
    def __init__(self, pos):
        self.pos = V2(pos)
        self.vel = V2()
        self.target = V2(pos)
        self.radius = FROG_RADIUS
        self.speed = FROG_SPEED
        self.facing = V2(1, 0)   # used to aim bubbles when frog is not moving
        self.bubbles = []

        # Hurt state setup. When hurt_timer > 0 the frog cannot be hit again.
        self.hurt_timer = 0.0

        # Debug visualization attributes
        self.last_steer = V2()

    def set_target(self, p):
        """Set a new target the frog will move toward using Arrive."""
        self.target = V2(p)

    def shoot(self):
        """Spawn a bubble just in front of the frog, moving along the facing direction."""
        dir_vec = self.vel if self.vel.length_squared() > 1 else self.facing
        origin = self.pos + dir_vec.normalize() * (self.radius + 6)
        self.bubbles.append(Bubble(origin, dir_vec))

    def start_hurt(self):
        """Begin the invulnerability window after damage."""
        if self.hurt_timer <= 0:
            self.hurt_timer = HURT_INVULN

    def can_be_hurt(self):
        """Return True if the frog can take damage right now."""
        return self.hurt_timer <= 0

    def update(self, dt):
        # Compute steering with Arrive
        steer = arrive(self.pos, self.vel, self.target, self.speed)
        self.last_steer = V2(steer)

        # Integrate velocity with dt and clamp to max speed
        self.vel = integrate_velocity(self.vel, steer, dt, self.speed)

        # Move the frog
        self.pos += self.vel * dt

        # Face in the direction of motion when moving
        if self.vel.length_squared() > 16:
            self.facing = self.vel.normalize()

        # Keep inside bounds
        self.pos.x = clamp(self.pos.x, self.radius, WIDTH - self.radius)
        self.pos.y = clamp(self.pos.y, self.radius, HEIGHT - self.radius)

        # Update bubbles and remove popped ones
        for b in list(self.bubbles):
            b.update(dt)
            if not b.alive:
                self.bubbles.remove(b)

        # Count down invulnerability
        if self.hurt_timer > 0:
            self.hurt_timer -= dt

    def draw(self, surf):
        # Flash while hurt. This provides player feedback and helps debugging.
        color = GREEN
        if self.hurt_timer > 0:
            t = int(pygame.time.get_ticks() * 0.01) % 2
            color = (220, 220, 220) if t == 0 else (160, 160, 160)

        # Calculate squash & stretch scales based on speed & arrival deceleration
        spd = self.vel.length()
        spd_ratio = min(1.0, spd / self.speed)
        dist_to_target = (self.target - self.pos).length()
        is_landing = (dist_to_target < ARRIVE_SLOW_RADIUS and spd_ratio < 0.45 and dist_to_target > ARRIVE_STOP_RADIUS)

        if is_landing:
            # Landing impact squash (wider perpendicular, flatter along motion)
            rx = int(self.radius * 1.20)
            ry = int(self.radius * 0.82)
        else:
            # High-speed stretch (longer along motion, narrower perpendicular)
            rx = int(self.radius * (1.0 + 0.24 * spd_ratio))
            ry = int(self.radius * (1.0 - 0.18 * spd_ratio))

        rx, ry = max(4, rx), max(4, ry)

        # Create deformed body surface & rotate along facing angle
        angle_deg = math.degrees(math.atan2(self.facing.y, self.facing.x))
        max_dim = max(rx, ry) * 2 + 8
        body_surf = pygame.Surface((max_dim, max_dim), pygame.SRCALPHA)
        center = (max_dim // 2, max_dim // 2)

        # Ground shadow
        sh_rect = pygame.Rect(center[0] - rx + 2, center[1] - ry + 3, rx * 2, ry * 2)
        pygame.draw.ellipse(body_surf, (0, 0, 0, 45), sh_rect)
        # Deformed body
        body_rect = pygame.Rect(center[0] - rx, center[1] - ry, rx * 2, ry * 2)
        pygame.draw.ellipse(body_surf, color, body_rect)

        # Rotate body surface to facing direction
        rot_surf = pygame.transform.rotate(body_surf, -angle_deg)
        rot_rect = rot_surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        surf.blit(rot_surf, rot_rect)

        # Eye looks in facing direction
        eye = self.pos + self.facing * (self.radius - 4)
        pygame.draw.circle(surf, WHITE, eye, 5)
        pygame.draw.circle(surf, (30, 30, 30), eye, 2)

        # Bubbles
        for b in self.bubbles:
            b.draw(surf)

    def draw_target_marker(self, surf):
        """Render a subtle pulsing lily pad target marker at destination until frog arrives."""
        dist = (self.target - self.pos).length()
        if dist > ARRIVE_STOP_RADIUS + 4:
            tx, ty = int(self.target.x), int(self.target.y)
            t = pygame.time.get_ticks() * 0.005
            pulse_r = int(12 + math.sin(t) * 3)
            
            # Soft translucent ring
            ring_surf = pygame.Surface((pulse_r * 2 + 4, pulse_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, (100, 240, 150, 110), (pulse_r + 2, pulse_r + 2), pulse_r, 2)
            pygame.draw.circle(ring_surf, (100, 240, 150, 180), (pulse_r + 2, pulse_r + 2), 3)
            surf.blit(ring_surf, (tx - pulse_r - 2, ty - pulse_r - 2))

    def draw_debug(self, surf, font):
        """Render AI debug visualization overlay for the Frog when debug_mode is ON."""
        tx, ty = int(self.target.x), int(self.target.y)

        # 1. Arrive Target Crosshair & Deceleration / Stop Radii
        # Slow Radius Circle (120px)
        slow_surf = pygame.Surface((int(ARRIVE_SLOW_RADIUS * 2 + 4), int(ARRIVE_SLOW_RADIUS * 2 + 4)), pygame.SRCALPHA)
        pygame.draw.circle(slow_surf, (250, 225, 120, 60), (int(ARRIVE_SLOW_RADIUS + 2), int(ARRIVE_SLOW_RADIUS + 2)), int(ARRIVE_SLOW_RADIUS), 1)
        surf.blit(slow_surf, (tx - int(ARRIVE_SLOW_RADIUS) - 2, ty - int(ARRIVE_SLOW_RADIUS) - 2))

        # Stop Radius Circle (8px)
        pygame.draw.circle(surf, (250, 225, 120), (tx, ty), int(ARRIVE_STOP_RADIUS), 1)
        # Target crosshair
        pygame.draw.line(surf, (250, 225, 120), (tx - 8, ty), (tx + 8, ty), 2)
        pygame.draw.line(surf, (250, 225, 120), (tx, ty - 8), (tx, ty + 8), 2)

        # Target connection line
        pygame.draw.line(surf, (250, 225, 120, 120), self.pos, self.target, 1)

        # 2. Fly Threat Range (160px) around Frog
        threat_r = 160.0
        threat_surf = pygame.Surface((int(threat_r * 2 + 4), int(threat_r * 2 + 4)), pygame.SRCALPHA)
        pygame.draw.circle(threat_surf, (255, 200, 80, 40), (int(threat_r + 2), int(threat_r + 2)), int(threat_r), 1)
        surf.blit(threat_surf, (int(self.pos.x - threat_r - 2), int(self.pos.y - threat_r - 2)))

        # 3. Vectors (Velocity = BLUE, Steering = RED)
        if self.vel.length_squared() > 0:
            end_v = self.pos + self.vel * 0.4
            pygame.draw.line(surf, (80, 160, 255), self.pos, end_v, 2)
        if self.last_steer.length_squared() > 0:
            end_s = self.pos + self.last_steer * 0.4
            pygame.draw.line(surf, (255, 90, 90), self.pos, end_s, 2)

        # 4. State Text Label
        state_str = f"Frog: Hurt ({self.hurt_timer:.1f}s)" if self.hurt_timer > 0 else "Frog: Normal"
        txt = font.render(state_str, True, (160, 255, 160))
        surf.blit(txt, (int(self.pos.x - txt.get_width() // 2), int(self.pos.y - self.radius - 20)))
