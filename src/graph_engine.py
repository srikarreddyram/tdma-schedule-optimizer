"""Graph model and slot assignment for the TDMA schedule optimizer."""
import itertools
import math

import networkx as nx

DEFAULT_RANGE_M = 500.0
STRATEGIES = ("DSATUR", "largest_first")


def build_physical_graph(coords, radio_range=DEFAULT_RANGE_M):
    """Radios are nodes; an edge joins two radios within radio_range of each other."""
    graph = nx.Graph()
    graph.add_nodes_from(coords)
    for a, b in itertools.combinations(coords, 2):
        if math.dist(coords[a], coords[b]) <= radio_range:
            graph.add_edge(a, b)
    return graph


def build_conflict_graph(physical):
    """Join every pair of radios that are 1 or 2 hops apart in the physical graph.

    1 hop is direct interference; 2 hops is the hidden-terminal case, where
    both radios would collide at their common neighbour.
    """
    return nx.power(physical, 2)


def assign_slots(conflict, strategy):
    """Greedy-colour the conflict graph; each colour is one time slot."""
    colours = nx.greedy_color(conflict, strategy=strategy)
    return _renumber(colours, conflict.nodes)


def _renumber(colours, node_order):
    # Colour ids are arbitrary, so relabel them in order of first use: the
    # first node always gets slot 0 and the output is stable between runs.
    new_id = {}
    for node in node_order:
        new_id.setdefault(colours[node], len(new_id))
    return {node: new_id[colours[node]] for node in node_order}


def frame_length(slots):
    return max(slots.values()) + 1


def slot_lower_bound(physical):
    """No schedule can use fewer slots than this.

    A radio and all of its neighbours are pairwise within 2 hops (through that
    radio), so every one of them needs its own slot.
    """
    return max(degree for _, degree in physical.degree) + 1
