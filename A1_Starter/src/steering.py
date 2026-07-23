# ============================================================================
# steering.py
# Purpose
#   Implement all steering behaviours here. Each function computes a steering
#   force vector. Entities apply that force to their velocity each frame.
# Key idea
#   desired_velocity minus current_velocity gives the steering force.
#   Use dt in update loops when integrating velocity to keep motion consistent.
# ============================================================================

import math, random
from pygame.math import Vector2 as V2
from utils import limit, circlecast_hits_any_rect
from settings import (
    WIDTH, HEIGHT,
    ARRIVE_SLOW_RADIUS, ARRIVE_STOP_RADIUS,
    AVOID_LOOKAHEAD, AVOID_ANGLE_INCREMENT, AVOID_MAX_ANGLE,
    FLY_SPEED
)

# ---------------- Base behaviours ----------------

def seek(pos, vel, target, max_speed):
    """
    Move toward a target. Returns a steering force.
    desired = direction_to_target * max_speed
    steering = desired - current_velocity
    """
    d = target - pos
    if d.length_squared() == 0:
        return V2()
    desired = d.normalize() * max_speed
    return desired - vel

def flee(pos, vel, target, max_speed):
    """
    Move away from a target. This is the opposite of seek.
    Desired velocity points from the target toward self, at max_speed.
    steering = desired - current_velocity
    """
    d = pos - target
    if d.length_squared() == 0:
        return V2()
    desired = d.normalize() * max_speed
    return desired - vel

def arrive(pos, vel, target, max_speed, slow_radius=ARRIVE_SLOW_RADIUS, stop_radius=ARRIVE_STOP_RADIUS):
    """
    Like seek when far, but slow down near the target.
    Rules
      If distance < stop_radius, return a force that cancels leftover velocity
      If distance < slow_radius, scale desired speed by distance / slow_radius
      Otherwise use full speed
    This should remove overshoot and jitter around the target.
    """
    d = target - pos
    dist = d.length()
    # Inside stop radius: brake to zero
    if dist < stop_radius:
        return -vel
    # Inside slow radius: linearly scale speed down
    if dist < slow_radius:
        desired = d.normalize() * max_speed * (dist / slow_radius)
    else:
        desired = d.normalize() * max_speed
    return desired - vel

def integrate_velocity(vel, force, dt, max_speed):
    """
    Apply a steering force to velocity using Euler integration.
    Then clamp to max speed and return the new velocity.
    Use this inside agent update methods after computing steering forces.
    """
    vel += limit(force, 500.0) * dt
    if vel.length() > max_speed:
        vel.scale_to_length(max_speed)
    return vel

# ---------------- Boids components ----------------

def boids_separation(me_pos, neighbors, sep_radius):
    """
    Push away from neighbors that are too close.
    neighbors: list of tuples (neighbor_pos, neighbor_vel)
    Accumulate (me - neighbor) / dist² for each neighbor inside sep_radius,
    then normalize the result and scale to FLY_SPEED.
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
    Pull toward the average position of neighbors.
    Compute the center of mass of all neighbors, then return a normalized
    vector pointing from me toward that center, scaled to FLY_SPEED.
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
    Match the average velocity of neighbors.
    Compute the average velocity of all neighbors, then return a normalized
    vector in that direction, scaled to FLY_SPEED.
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

# ---------------- Obstacle avoidance blend ----------------

def seek_with_avoid(pos, vel, target, max_speed, radius, rects, lookahead=AVOID_LOOKAHEAD, debug_out=None):
    """
    Seek the target but avoid obstacles by sampling angled corridors.
    If debug_out is provided, populates debug_out['rays'] with (start_pos, end_pos, is_blocked)
    and debug_out['chosen'] with the selected target endpoint.
    """
    d = target - pos
    if d.length_squared() == 0:
        return V2()
    direction = d.normalize()
    base_reach = min(lookahead, d.length())

    if debug_out is not None:
        debug_out['rays'] = []
        debug_out['chosen'] = None

    # Try different lookahead lengths (base, half, and a very short 42px corridor)
    # to find any escape routes in tight gaps/corners.
    for reach in [base_reach, base_reach * 0.5, 42.0]:
        end_point = pos + direction * reach
        
        if vel.length_squared() > 1e-3:
            heading = vel.normalize()
        else:
            heading = direction

        # Step 1: check straight corridor to target
        hit_straight = circlecast_hits_any_rect(pos, end_point, radius, rects, ignore_start=True)
        if debug_out is not None:
            debug_out['rays'].append((V2(pos), V2(end_point), hit_straight))

        if not hit_straight:
            if debug_out is not None:
                debug_out['chosen'] = V2(target)
            return seek(pos, vel, target, max_speed)

        # Step 2-3: try angled corridors relative to current heading up to 96 degrees
        max_scan_angle = 96
        for angle in range(AVOID_ANGLE_INCREMENT, max_scan_angle + 1, AVOID_ANGLE_INCREMENT):
            # Clockwise
            rot_r = heading.rotate(angle)
            end_r = pos + rot_r * reach
            hit_r = circlecast_hits_any_rect(pos, end_r, radius, rects, ignore_start=True)
            if debug_out is not None:
                debug_out['rays'].append((V2(pos), V2(end_r), hit_r))
            if not hit_r:
                if debug_out is not None:
                    debug_out['chosen'] = V2(end_r)
                return seek(pos, vel, end_r, max_speed)

            # Counter-clockwise
            rot_l = heading.rotate(-angle)
            end_l = pos + rot_l * reach
            hit_l = circlecast_hits_any_rect(pos, end_l, radius, rects, ignore_start=True)
            if debug_out is not None:
                debug_out['rays'].append((V2(pos), V2(end_l), hit_l))
            if not hit_l:
                if debug_out is not None:
                    debug_out['chosen'] = V2(end_l)
                return seek(pos, vel, end_l, max_speed)

    # Step 4: all corridors blocked, steer away from map edges toward center
    center = V2(WIDTH * 0.5, HEIGHT * 0.5)
    if debug_out is not None:
        debug_out['chosen'] = V2(center)
    return seek(pos, vel, center, max_speed)

# ---------------- New behaviours to be implemented ----------------

_wander_angles = {}

def pursue(pos, vel, target_pos, target_vel, max_speed, max_prediction=0.6):
    """
    Predict the future position of the target then seek that point.
    Cap time_horizon to max_prediction to prevent target projecting into walls.
    """
    d = target_pos - pos
    dist = d.length()
    time_horizon = min(dist / (max_speed + 1e-5), max_prediction)
    predicted = target_pos + target_vel * time_horizon
    return seek(pos, vel, predicted, max_speed)

def evade(pos, vel, threat_pos, threat_vel, max_speed, max_prediction=0.6):
    """
    Predict the future position of a threat then flee from that point.
    Cap time_horizon to max_prediction to prevent over-reacting.
    """
    d = threat_pos - pos
    dist = d.length()
    time_horizon = min(dist / (max_speed + 1e-5), max_prediction)
    predicted = threat_pos + threat_vel * time_horizon
    return flee(pos, vel, predicted, max_speed)

def wander_force(me_vel, jitter_deg=12.0, circle_distance=24.0, circle_radius=18.0, rng_seed=None):
    """
    Return a small random steering vector for gentle drift.
    Classic wander:
      Project a small circle ahead along current heading, then jitter the
      target point on that circle by a tiny random angle each update.
    """
    global _wander_angles
    # Use rng_seed as a key to keep track of the unique wander angle for each agent
    key = rng_seed if rng_seed is not None else 0
    if key not in _wander_angles:
        # Initialize randomly if first time
        _wander_angles[key] = random.uniform(0, 360)
    
    # Jitter the angle by a small amount
    _wander_angles[key] += random.uniform(-jitter_deg, jitter_deg)
    
    # Calculate heading
    if me_vel.length_squared() > 0:
        heading = me_vel.normalize()
    else:
        heading = V2(1, 0)
        
    circle_center = heading * circle_distance
    displacement = heading.rotate(_wander_angles[key]) * circle_radius
    return circle_center + displacement

def seek_through_gap(pos, vel, target, gap_midpoint, max_speed, approach_radius=60.0):
    """
    Two-phase steering for threading through a narrow gap between obstacles.
    Phase 1 (Approach): Use arrive() toward gap entrance to decelerate and
        gradually align the heading toward the corridor opening.
    Phase 2 (Thread):  Once close and aligned, switch to seek() through
        the gap toward the final target position.
    """
    to_gap = gap_midpoint - pos
    dist_to_gap = to_gap.length()

    # Phase 2: Close to gap entrance — check alignment before threading through
    if dist_to_gap <= approach_radius:
        gap_to_target = target - gap_midpoint
        if vel.length_squared() > 1e-3 and gap_to_target.length_squared() > 1e-3:
            heading = vel.normalize()
            thread_dir = gap_to_target.normalize()
            alignment = heading.dot(thread_dir)
            if alignment > 0.5:
                # Aligned within ~60°: commit through the gap toward the frog
                return seek(pos, vel, target, max_speed)
        # Not yet aligned: keep arriving at gap midpoint to correct heading
        return arrive(pos, vel, gap_midpoint, max_speed * 0.6,
                      slow_radius=50.0, stop_radius=8.0)

    # Phase 1: Far from gap — arrive toward gap entrance with deceleration
    return arrive(pos, vel, gap_midpoint, max_speed * 0.85,
                  slow_radius=80.0, stop_radius=12.0)
