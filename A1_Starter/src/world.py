import random
import pygame

class World:
    def __init__(self, width, height):
        self.rect = pygame.Rect(0, 0, width, height)
        self.obstacles = []
        self._build_obstacles(width, height)

    def _build_obstacles(self, w, h):
        """Create a fixed set of obstacle rectangles using a seeded random generator."""
        rng = random.Random(9)
        for _ in range(9):
            ww = rng.randint(80, 180)
            hh = rng.randint(60, 140)
            x = rng.randint(40, w - ww - 40)
            y = rng.randint(40, h - hh - 40)
            rect = pygame.Rect(x, y, ww, hh)
            self.obstacles.append(rect)

    def draw(self, surf):
        """Render each obstacle rectangle with safety buffer outline and styled borders."""
        for r in self.obstacles:
            buf_r = r.inflate(14, 14)
            b_surf = pygame.Surface((buf_r.width + 4, buf_r.height + 4), pygame.SRCALPHA)
            b_rect = pygame.Rect(2, 2, buf_r.width, buf_r.height)
            pygame.draw.rect(b_surf, (120, 160, 190, 45), b_rect, 2, border_radius=12)
            surf.blit(b_surf, (buf_r.x - 2, buf_r.y - 2))

            pygame.draw.rect(surf, (70, 85, 95), r, border_radius=10)
            pygame.draw.rect(surf, (110, 130, 145), r, 2, border_radius=10)
