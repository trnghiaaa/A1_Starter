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

def segment_circlecast_hits_rect(p0, p1, radius, rect, step=6.0, ignore_start=False):
    """
    Approximate a circle cast along a line from p0 to p1.
    We sample points along the segment and test a circle intersect at each step.
    """
    d = p1 - p0
    length = d.length()
    if length == 0:
        return circle_rect_intersect(p0, radius, rect)
    n = max(1, int(length / step))
    start_idx = 1 if ignore_start else 0
    for i in range(start_idx, n + 1):
        t = i / n
        pos = p0 + d * t
        if circle_rect_intersect(pos, radius, rect):
            return True
    return False

def circle_outside_bounds(center, radius):
    """Return True if a circle with the given center and radius goes outside the screen."""
    return (center.x - radius < 0 or 
            center.x + radius > WIDTH or 
            center.y - radius < 0 or 
            center.y + radius > HEIGHT)

def circlecast_hits_any_rect(p0, p1, radius, rects, step=6.0, ignore_start=False):
    """Return True if the swept circle between p0 and p1 hits any rect in the list or the screen bounds."""
    # Check if the corridor goes outside the screen boundaries
    d = p1 - p0
    length = d.length()
    if length == 0:
        if not ignore_start and circle_outside_bounds(p0, radius):
            return True
    else:
        n = max(1, int(length / step))
        start_idx = 1 if ignore_start else 0
        for i in range(start_idx, n + 1):
            pos = p0 + d * (i / n)
            if circle_outside_bounds(pos, radius):
                return True

    # Check rectangular obstacles
    for r in rects:
        if segment_circlecast_hits_rect(p0, p1, radius, r, step, ignore_start):
            return True
    return False

def has_line_of_sight(p0, p1, rects, ray_radius=3.0):
    """
    Return True if there is an unobstructed line of sight between p0 and p1.
    Returns False if any obstacle rectangle blocks the direct vision path.
    """
    for r in rects:
        if segment_circlecast_hits_rect(p0, p1, ray_radius, r, step=4.0, ignore_start=True):
            return False
    return True

def find_corridor_gaps(rects, max_gap_width=120, min_gap_width=42):
    """
    Detect narrow gaps (corridors) between pairs of obstacle rectangles.
    Checks facing edges for both horizontal and vertical gaps.
    Returns a list of (gap_midpoint_V2, gap_direction_V2, gap_width) tuples.
    gap_direction indicates the traversal axis through the corridor.
    """
    gaps = []
    n = len(rects)
    for i in range(n):
        for j in range(i + 1, n):
            A, B = rects[i], rects[j]

            # --- Vertical gap (A above B): corridor runs top-to-bottom ---
            if A.bottom < B.top:
                gap_w = B.top - A.bottom
                if min_gap_width <= gap_w <= max_gap_width:
                    # Require horizontal overlap between the two rects
                    ol = max(A.left, B.left)
                    or_ = min(A.right, B.right)
                    if or_ > ol:
                        mid = V2((ol + or_) / 2, (A.bottom + B.top) / 2)
                        # Ensure gap midpoint is not inside a third obstacle
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(0, 1), gap_w))

            # --- Vertical gap (B above A) ---
            if B.bottom < A.top:
                gap_w = A.top - B.bottom
                if min_gap_width <= gap_w <= max_gap_width:
                    ol = max(A.left, B.left)
                    or_ = min(A.right, B.right)
                    if or_ > ol:
                        mid = V2((ol + or_) / 2, (B.bottom + A.top) / 2)
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(0, 1), gap_w))

            # --- Horizontal gap (A left of B): corridor runs left-to-right ---
            if A.right < B.left:
                gap_w = B.left - A.right
                if min_gap_width <= gap_w <= max_gap_width:
                    ot = max(A.top, B.top)
                    ob = min(A.bottom, B.bottom)
                    if ob > ot:
                        mid = V2((A.right + B.left) / 2, (ot + ob) / 2)
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(1, 0), gap_w))

            # --- Horizontal gap (B left of A) ---
            if B.right < A.left:
                gap_w = A.left - B.right
                if min_gap_width <= gap_w <= max_gap_width:
                    ot = max(A.top, B.top)
                    ob = min(A.bottom, B.bottom)
                    if ob > ot:
                        mid = V2((B.right + A.left) / 2, (ot + ob) / 2)
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(1, 0), gap_w))

    return gaps

def ray_screen_edge_intersection(origin, direction, margin=26):
    """
    Calculate the boundary coordinate where a ray from origin along direction
    hits the screen viewport rectangle [margin, margin, WIDTH - margin, HEIGHT - margin].
    """
    if direction.length_squared() == 0:
        return V2(origin)
    dir_n = direction.normalize()
    min_x, max_x = float(margin), float(WIDTH - margin)
    min_y, max_y = float(margin), float(HEIGHT - margin)

    t_candidates = []
    if dir_n.x > 1e-5:
        t_candidates.append((max_x - origin.x) / dir_n.x)
    elif dir_n.x < -1e-5:
        t_candidates.append((min_x - origin.x) / dir_n.x)

    if dir_n.y > 1e-5:
        t_candidates.append((max_y - origin.y) / dir_n.y)
    elif dir_n.y < -1e-5:
        t_candidates.append((min_y - origin.y) / dir_n.y)

    valid_t = [t for t in t_candidates if t > 0]
    if not valid_t:
        return V2(origin)

    t_hit = min(valid_t)
    hit_pt = origin + dir_n * t_hit
    hit_pt.x = clamp(hit_pt.x, min_x, max_x)
    hit_pt.y = clamp(hit_pt.y, min_y, max_y)
    return hit_pt
