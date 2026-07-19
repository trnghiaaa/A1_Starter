# ============================================================================
# world.py
# Purpose
#   Build the arena and a list of rectangular obstacles.
#   Obstacles are static and are used by the snake for avoidance checks.
# Why rectangles
#   Rectangles are easy to draw and fast to test against with our helpers.
# ============================================================================

import random
import pygame

class World:
    def __init__(self, width, height):
        # Whole world bounds as a pygame.Rect for convenience
        self.rect = pygame.Rect(0, 0, width, height)

        # Container that holds all blocking rectangles
        self.obstacles = []

        # Build a reproducible obstacle set
        self._build_obstacles(width, height)

    def _build_obstacles(self, w, h):
        """Create a few rectangles with a fixed random seed for reproducibility."""
        rng = random.Random(9)
        for _ in range(9):
            ww = rng.randint(80, 180)
            hh = rng.randint(60, 140)
            x = rng.randint(40, w - ww - 40)
            y = rng.randint(40, h - hh - 40)
            rect = pygame.Rect(x, y, ww, hh)
            self.obstacles.append(rect)

    def draw(self, surf):
        """Render each obstacle with a fill and a subtle outline."""
        for r in self.obstacles:
            pygame.draw.rect(surf, (70, 85, 95), r, border_radius=10)
            pygame.draw.rect(surf, (110, 130, 145), r, 2, border_radius=10)
