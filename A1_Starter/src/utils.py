# ============================================================================
# utils.py
# Purpose
#   Small helper functions that do not belong to a specific agent.
#   Drawing helpers and collision checks live here.
# Notes
#   None of these helpers should change game rules or AI decisions.
# ============================================================================

import pygame
from pygame.math import Vector2 as V2
from settings import WIDTH, HEIGHT

# A soft grid color for the background
GRID = (36, 42, 48)

def draw_grid(surf):
    """
    Draw a light grid to help the eye judge motion and distance.
    The grid has no effect on gameplay. It is only visual.
    """
    gap = 36  # distance between grid lines
    # Draw vertical lines
    for x in range(0, WIDTH, gap):
        pygame.draw.line(surf, GRID, (x, 0), (x, HEIGHT))
    # Draw horizontal lines
    for y in range(0, HEIGHT, gap):
        pygame.draw.line(surf, GRID, (0, y), (WIDTH, y))

def clamp(x, a, b):
    """Limit a scalar value x so it stays between a and b inclusive."""
    return max(a, min(b, x))

def limit(v, max_len):
    """
    Limit a vector length.
    If v is longer than max_len, scale it down to exactly max_len.
    """
    if v.length_squared() > max_len * max_len:
        v.scale_to_length(max_len)
    return v

def nearest_point_on_rect(point, rect):
    """Return the closest point on an axis aligned rectangle to a given point."""
    x = clamp(point.x, rect.left, rect.right)
    y = clamp(point.y, rect.top, rect.bottom)
    return V2(x, y)

def circle_rect_intersect(center, radius, rect):
    """Return True if a circle touches or overlaps a rectangle."""
    np = nearest_point_on_rect(center, rect)
    return (center - np).length_squared() <= radius * radius

def segment_circlecast_hits_rect(p0, p1, radius, rect, step=6.0):
    """
    Approximate a circle cast along a line from p0 to p1.
    We sample points along the segment and test a circle intersect at each step.
    """
    d = p1 - p0
    length = d.length()
    if length == 0:
        return circle_rect_intersect(p0, radius, rect)
    n = max(1, int(length / step))
    for i in range(n + 1):
        t = i / n
        pos = p0 + d * t
        if circle_rect_intersect(pos, radius, rect):
            return True
    return False

def circlecast_hits_any_rect(p0, p1, radius, rects, step=6.0):
    """Return True if the swept circle between p0 and p1 hits any rect in the list."""
    for r in rects:
        if segment_circlecast_hits_rect(p0, p1, radius, r, step):
            return True
    return False
