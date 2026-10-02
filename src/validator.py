"""Collision self-check for a TDMA schedule.

Works from the raw coordinates rather than the conflict graph built in
graph_engine, so a bug in the graph construction cannot hide a collision.
"""
import itertools
import math


def find_collisions(coords, slots, radio_range):
    """Return (node_a, node_b, reason) for every pair that shares a slot but must not."""
    neighbours = {
        a: {b for b in coords if b != a and math.dist(coords[a], coords[b]) <= radio_range}
        for a in coords
    }
    collisions = []
    for a, b in itertools.combinations(coords, 2):
        if slots[a] != slots[b]:
            continue
        if b in neighbours[a]:
            collisions.append((a, b, "direct link (1-hop)"))
            continue
        shared = neighbours[a] & neighbours[b]
        if shared:
            collisions.append((a, b, f"hidden terminal (2-hop) at {sorted(shared)[0]}"))
    return collisions
