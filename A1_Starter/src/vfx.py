# ============================================================================
# vfx.py
# Purpose
#   Particle visual effects system, floating text popups, and screen shake.
# ============================================================================

import random, math
import pygame
from pygame.math import Vector2 as V2

class Particle:
    def __init__(self, pos, vel, color, radius, lifetime, shrink=True, fade=True):
        self.pos = V2(pos)
        self.vel = V2(vel)
        self.color = list(color)
        self.radius = float(radius)
        self.initial_radius = float(radius)
        self.lifetime = float(lifetime)
        self.max_lifetime = float(lifetime)
        self.shrink = shrink
        self.fade = fade
        self.alive = True

    def update(self, dt):
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return
        
        self.pos += self.vel * dt
        self.vel *= 0.92  # Air drag

        if self.shrink:
            progress = max(0.0, self.lifetime / self.max_lifetime)
            self.radius = self.initial_radius * progress

    def draw(self, surf):
        if not self.alive or self.radius <= 0.5:
            return
        progress = max(0.0, min(1.0, self.lifetime / self.max_lifetime))
        alpha = int(255 * progress) if self.fade else 255
        
        r = int(self.radius)
        if r < 1: r = 1
        p_surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        c = (self.color[0], self.color[1], self.color[2], alpha)
        pygame.draw.circle(p_surf, c, (r + 1, r + 1), r)
        surf.blit(p_surf, (self.pos.x - r - 1, self.pos.y - r - 1))


class FloatingText:
    def __init__(self, pos, text, color=(255, 240, 100), font=None):
        self.pos = V2(pos)
        self.text = text
        self.color = color
        self.font = font
        self.lifetime = 0.65
        self.max_lifetime = 0.65
        self.alive = True

    def update(self, dt):
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return
        self.pos.y -= 40.0 * dt  # Float upwards

    def draw(self, surf):
        if not self.alive or not self.font:
            return
        progress = max(0.0, min(1.0, self.lifetime / self.max_lifetime))
        alpha = int(255 * progress)
        text_surf = self.font.render(self.text, True, self.color)
        text_surf.set_alpha(alpha)
        surf.blit(text_surf, (int(self.pos.x - text_surf.get_width() // 2), int(self.pos.y - text_surf.get_height() // 2)))


class VFXManager:
    def __init__(self, font=None):
        self.particles = []
        self.floating_texts = []
        self.screen_shake = 0.0
        self.font = font

    def update(self, dt):
        if self.screen_shake > 0:
            self.screen_shake = max(0.0, self.screen_shake - dt)

        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        for ft in self.floating_texts:
            ft.update(dt)
        self.floating_texts = [ft for ft in self.floating_texts if ft.alive]

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)
        for ft in self.floating_texts:
            ft.draw(surf)

    def trigger_shake(self, duration=0.25):
        self.screen_shake = max(self.screen_shake, duration)

    def get_shake_offset(self):
        if self.screen_shake <= 0:
            return (0, 0)
        intensity = self.screen_shake * 14.0
        return (random.uniform(-intensity, intensity), random.uniform(-intensity, intensity))

    def add_bubble_pop(self, pos):
        for _ in range(10):
            angle = random.uniform(0, math.pi * 2)
            spd = random.uniform(40, 170)
            vel = V2(math.cos(angle) * spd, math.sin(angle) * spd)
            color = (180, 230, 255)
            radius = random.uniform(2.5, 5.0)
            lifetime = random.uniform(0.2, 0.45)
            self.particles.append(Particle(pos, vel, color, radius, lifetime))

    def add_eat_fly(self, pos):
        if self.font:
            self.floating_texts.append(FloatingText(pos, "+1", color=(255, 240, 100), font=self.font))
        for _ in range(8):
            angle = random.uniform(0, math.pi * 2)
            spd = random.uniform(30, 130)
            vel = V2(math.cos(angle) * spd, math.sin(angle) * spd)
            color = random.choice([(255, 230, 100), (160, 235, 120), (255, 255, 200)])
            radius = random.uniform(2.0, 4.5)
            lifetime = random.uniform(0.25, 0.5)
            self.particles.append(Particle(pos, vel, color, radius, lifetime))

    def add_hurt_impact(self, pos):
        self.trigger_shake(0.3)
        for _ in range(14):
            angle = random.uniform(0, math.pi * 2)
            spd = random.uniform(60, 220)
            vel = V2(math.cos(angle) * spd, math.sin(angle) * spd)
            color = (255, 80, 80)
            radius = random.uniform(3.0, 6.0)
            lifetime = random.uniform(0.3, 0.55)
            self.particles.append(Particle(pos, vel, color, radius, lifetime))
