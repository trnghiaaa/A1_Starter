import math, random
from pygame.math import Vector2 as V2
from utils import limit, circlecast_hits_any_rect
from settings import (
    WIDTH, HEIGHT,
    ARRIVE_SLOW_RADIUS, ARRIVE_STOP_RADIUS,
    AVOID_LOOKAHEAD, AVOID_ANGLE_INCREMENT, AVOID_MAX_ANGLE,
    FLY_SPEED
)

# ---------------- Base Behaviors ----------------

def seek(pos, vel, target, max_speed):
    """
    Compute steering force to move toward a target position.
    steering = desired_velocity - current_velocity
    """
    d = target - pos
    if d.length_squared() == 0:
        return V2()
    desired = d.normalize() * max_speed
    return desired - vel

def flee(pos, vel, target, max_speed):
    """
    Compute steering force to move away from a target position.
    steering = desired_velocity - current_velocity
    """
    d = pos - target
    if d.length_squared() == 0:
        return V2()
    desired = d.normalize() * max_speed
    return desired - vel

def arrive(pos, vel, target, max_speed, slow_radius=ARRIVE_SLOW_RADIUS, stop_radius=ARRIVE_STOP_RADIUS, dt=0.016):
    """
    Compute steering force to move toward a target while decelerating near arrival.
    Uses square-root deceleration curve for smooth stopping without overshoot.
    """
    d = target - pos
    dist = d.length()
    if dist <= stop_radius:
        return -vel / max(dt, 1e-4)

    if dist < slow_radius:
        t = max(0.0, min(1.0, (dist - stop_radius) / max(1.0, slow_radius - stop_radius)))
        speed_factor = math.sqrt(t)
        desired = d.normalize() * max_speed * speed_factor
        return (desired - vel) * 2.2
    else:
        desired = d.normalize() * max_speed
        return desired - vel

def integrate_velocity(vel, force, dt, max_speed, max_force=650.0):
    """
    Apply steering force to velocity using Euler integration and clamp to max_speed.
    max_force caps steering acceleration magnitude for natural turning inertia.
    """
    vel += limit(force, max_force) * dt
    if vel.length() > max_speed:
        vel.scale_to_length(max_speed)
    return vel

# ---------------- Boids Behaviors ----------------

def boids_separation(me_pos, neighbors, sep_radius):
    """
    Compute separation force vector pushing away from nearby neighbors inside sep_radius.
    Accumulates (me - neighbor) / dist² for all neighbors.
    """
    raw = V2()
    for n_pos, _ in neighbors:
        diff = me_pos - n_pos
        dist = diff.length()
        if 0 < dist < sep_radius:
            raw += diff / (dist * dist)
    if raw.length_squared() > 0:
        return raw.normalize() * FLY_SPEED
    return V2()

def boids_cohesion(me_pos, neighbors):
    """
    Compute cohesion force vector steering toward the average position of neighbors.
    """
    if not neighbors:
        return V2()
    avg = V2()
    for n_pos, _ in neighbors:
        avg += n_pos
    avg /= len(neighbors)
    raw = avg - me_pos
    if raw.length_squared() > 0:
        return raw.normalize() * FLY_SPEED
    return V2()

def boids_alignment(me_vel, neighbors):
    """
    Compute alignment force vector matching the average velocity of neighbors.
    """
    if not neighbors:
        return V2()
    avg = V2()
    for _, n_vel in neighbors:
        avg += n_vel
    avg /= len(neighbors)
    if avg.length_squared() > 0:
        return avg.normalize() * FLY_SPEED
    return V2()

# ---------------- Obstacle Avoidance ----------------

def seek_with_avoid(pos, vel, target, max_speed, radius, rects, lookahead=AVOID_LOOKAHEAD, debug_out=None):
    """
    Seek target while avoiding obstacles by probing angled ray corridors.
    Populates debug_out dictionaries if provided for visualization.
    """
    d = target - pos
    if d.length_squared() == 0:
        return V2()
    direction = d.normalize()
    base_reach = min(lookahead, d.length())

    if debug_out is not None:
        debug_out['rays'] = []
        debug_out['chosen'] = None

    # Probe varying lookahead distances for tight gap traversal
    for reach in [base_reach, base_reach * 0.5, 42.0]:
        end_point = pos + direction * reach
        
        if vel.length_squared() > 1e-3:
            heading = vel.normalize()
        else:
            heading = direction

        # Probe straight corridor toward target
        hit_straight = circlecast_hits_any_rect(pos, end_point, radius, rects, ignore_start=True)
        if debug_out is not None:
            debug_out['rays'].append((V2(pos), V2(end_point), hit_straight))

        if not hit_straight:
            if debug_out is not None:
                debug_out['chosen'] = V2(target)
            return seek(pos, vel, target, max_speed)

        # Probe alternating angled corridors relative to heading
        max_scan_angle = 96
        for angle in range(AVOID_ANGLE_INCREMENT, max_scan_angle + 1, AVOID_ANGLE_INCREMENT):
            # Clockwise probe
            rot_r = heading.rotate(angle)
            end_r = pos + rot_r * reach
            hit_r = circlecast_hits_any_rect(pos, end_r, radius, rects, ignore_start=True)
            if debug_out is not None:
                debug_out['rays'].append((V2(pos), V2(end_r), hit_r))
            if not hit_r:
                if debug_out is not None:
                    debug_out['chosen'] = V2(end_r)
                return seek(pos, vel, end_r, max_speed)

            # Counter-clockwise probe
            rot_l = heading.rotate(-angle)
            end_l = pos + rot_l * reach
            hit_l = circlecast_hits_any_rect(pos, end_l, radius, rects, ignore_start=True)
            if debug_out is not None:
                debug_out['rays'].append((V2(pos), V2(end_l), hit_l))
            if not hit_l:
                if debug_out is not None:
                    debug_out['chosen'] = V2(end_l)
                return seek(pos, vel, end_l, max_speed)

    # Fallback to arena center if all corridors are blocked
    center = V2(WIDTH * 0.5, HEIGHT * 0.5)
    if debug_out is not None:
        debug_out['chosen'] = V2(center)
    return seek(pos, vel, center, max_speed)

# ---------------- Predictive & Advanced Behaviors ----------------

_wander_angles = {}

def pursue(pos, vel, target_pos, target_vel, max_speed, max_prediction=0.6):
    """
    Predict target future position based on velocity and seek that position.
    """
    d = target_pos - pos
    dist = d.length()
    time_horizon = min(dist / (max_speed + 1e-5), max_prediction)
    predicted = target_pos + target_vel * time_horizon
    return seek(pos, vel, predicted, max_speed)

def evade(pos, vel, threat_pos, threat_vel, max_speed, max_prediction=0.6):
    """
    Predict threat future position based on velocity and flee from that position.
    """
    d = threat_pos - pos
    dist = d.length()
    time_horizon = min(dist / (max_speed + 1e-5), max_prediction)
    predicted = threat_pos + threat_vel * time_horizon
    return flee(pos, vel, predicted, max_speed)

def wander_force(me_vel, jitter_deg=12.0, circle_distance=24.0, circle_radius=18.0, rng_seed=None):
    """
    Compute a wandering steering force by jittering a target on a projected circle ahead.
    """
    global _wander_angles
    key = rng_seed if rng_seed is not None else 0
    if key not in _wander_angles:
        _wander_angles[key] = random.uniform(0, 360)
    
    _wander_angles[key] += random.uniform(-jitter_deg, jitter_deg)
    
    if me_vel.length_squared() > 0:
        heading = me_vel.normalize()
    else:
        heading = V2(1, 0)
        
    circle_center = heading * circle_distance
    displacement = heading.rotate(_wander_angles[key]) * circle_radius
    return circle_center + displacement

def seek_through_gap(pos, vel, target, gap_midpoint, max_speed, approach_radius=60.0):
    """
    Two-phase steering behavior for navigating through narrow corridor gaps.
    Phase 1: Approach gap entrance using arrive().
    Phase 2: Once aligned and close, commit through gap using seek().
    """
    to_gap = gap_midpoint - pos
    dist_to_gap = to_gap.length()

    if dist_to_gap <= approach_radius:
        gap_to_target = target - gap_midpoint
        if vel.length_squared() > 1e-3 and gap_to_target.length_squared() > 1e-3:
            heading = vel.normalize()
            thread_dir = gap_to_target.normalize()
            alignment = heading.dot(thread_dir)
            if alignment > 0.5:
                return seek(pos, vel, target, max_speed)
        return arrive(pos, vel, gap_midpoint, max_speed * 0.6,
                      slow_radius=50.0, stop_radius=8.0)

    return arrive(pos, vel, gap_midpoint, max_speed * 0.85,
                  slow_radius=80.0, stop_radius=12.0)
