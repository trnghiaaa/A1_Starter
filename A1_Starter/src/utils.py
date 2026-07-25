import pygame
from pygame.math import Vector2 as V2
from settings import WIDTH, HEIGHT

# Background grid visual styling
GRID = (36, 42, 48)

def draw_grid(surf):
    """Draw a soft background grid overlay for spatial perception."""
    gap = 36  # Distance between grid lines in pixels
    for x in range(0, WIDTH, gap):
        pygame.draw.line(surf, GRID, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, gap):
        pygame.draw.line(surf, GRID, (0, y), (WIDTH, y))

def clamp(x, a, b):
    """Clamp scalar value x within range [a, b]."""
    return max(a, min(b, x))

def limit(v, max_len):
    """
    Limit vector length to max_len.
    Returns a copy scaled down to max_len if it exceeds max_len.
    Does not mutate the input vector.
    """
    if v.length_squared() > max_len * max_len:
        return v.normalize() * max_len
    return V2(v)

def nearest_point_on_rect(point, rect):
    """Return the nearest point on an axis-aligned rectangle to a target point."""
    x = clamp(point.x, rect.left, rect.right)
    y = clamp(point.y, rect.top, rect.bottom)
    return V2(x, y)

def circle_rect_intersect(center, radius, rect):
    """Return True if a circle intersects or overlaps an axis-aligned rectangle."""
    np = nearest_point_on_rect(center, rect)
    return (center - np).length_squared() <= radius * radius

def segment_circlecast_hits_rect(p0, p1, radius, rect, step=6.0, ignore_start=False):
    """
    Swept circle collision test along segment [p0, p1] against a rectangle.
    Samples test points along the line segment at step intervals.
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
    """Return True if a circle intersects or exceeds the screen boundaries."""
    return (center.x - radius < 0 or 
            center.x + radius > WIDTH or 
            center.y - radius < 0 or 
            center.y + radius > HEIGHT)

def circlecast_hits_any_rect(p0, p1, radius, rects, step=6.0, ignore_start=False):
    """Return True if the swept circle between p0 and p1 intersects screen bounds or any obstacle."""
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

    for r in rects:
        if segment_circlecast_hits_rect(p0, p1, radius, r, step, ignore_start):
            return True
    return False

def has_line_of_sight(p0, p1, rects, ray_radius=3.0):
    """
    Return True if an unobstructed line of sight exists between p0 and p1.
    Returns False if any obstacle rectangle blocks the vision ray.
    """
    for r in rects:
        if segment_circlecast_hits_rect(p0, p1, ray_radius, r, step=4.0, ignore_start=True):
            return False
    return True

def find_corridor_gaps(rects, max_gap_width=120, min_gap_width=42):
    """
    Detect narrow passage corridors between obstacle rectangle pairs.
    Returns a list of (gap_midpoint_V2, gap_direction_V2, gap_width) tuples.
    """
    gaps = []
    n = len(rects)
    for i in range(n):
        for j in range(i + 1, n):
            A, B = rects[i], rects[j]

            # Vertical gap (A above B): corridor runs top-to-bottom
            if A.bottom < B.top:
                gap_w = B.top - A.bottom
                if min_gap_width <= gap_w <= max_gap_width:
                    ol = max(A.left, B.left)
                    or_ = min(A.right, B.right)
                    if or_ > ol:
                        mid = V2((ol + or_) / 2, (A.bottom + B.top) / 2)
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(0, 1), gap_w))

            # Vertical gap (B above A)
            if B.bottom < A.top:
                gap_w = A.top - B.bottom
                if min_gap_width <= gap_w <= max_gap_width:
                    ol = max(A.left, B.left)
                    or_ = min(A.right, B.right)
                    if or_ > ol:
                        mid = V2((ol + or_) / 2, (B.bottom + A.top) / 2)
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(0, 1), gap_w))

            # Horizontal gap (A left of B): corridor runs left-to-right
            if A.right < B.left:
                gap_w = B.left - A.right
                if min_gap_width <= gap_w <= max_gap_width:
                    ot = max(A.top, B.top)
                    ob = min(A.bottom, B.bottom)
                    if ob > ot:
                        mid = V2((A.right + B.left) / 2, (ot + ob) / 2)
                        if not any(rects[k].collidepoint(mid.x, mid.y) for k in range(n) if k != i and k != j):
                            gaps.append((mid, V2(1, 0), gap_w))

            # Horizontal gap (B left of A)
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
    Calculate the viewport boundary intersection point for a ray starting at origin along direction.
    Clamps the point to [margin, margin, WIDTH - margin, HEIGHT - margin].
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
