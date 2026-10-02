"""Command-line entry point for the TDMA schedule optimizer."""
import argparse
import json
import sys
from pathlib import Path

from formatter import format_report
from graph_engine import (
    DEFAULT_RANGE_M,
    STRATEGIES,
    assign_slots,
    build_conflict_graph,
    build_physical_graph,
    frame_length,
    slot_lower_bound,
)
from validator import find_collisions


def parse_coords(text):
    """Turn '{"Node_01": [x, y], ...}' into {name: (x, y)}, rejecting anything else."""
    data = json.loads(text)
    if not isinstance(data, dict) or not data:
        raise ValueError("expected a non-empty JSON object of node name -> [x, y]")
    coords = {}
    for name, point in data.items():
        is_xy = (
            isinstance(point, list)
            and len(point) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in point)
        )
        if not is_xy:
            raise ValueError(f"{name}: expected [x, y], got {point!r}")
        coords[name] = (float(point[0]), float(point[1]))
    return coords


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute a conflict-free TDMA schedule using distance-2 graph colouring."
    )
    parser.add_argument("coords", nargs="?", help='JSON string: {"Node_01":[0.0,0.0], ...}')
    parser.add_argument("--file", type=Path, help="read the JSON coordinates from a file instead")
    parser.add_argument("--range", type=float, default=DEFAULT_RANGE_M, dest="radio_range",
                        help="radio range in meters (default: %(default)s)")
    args = parser.parse_args(argv)

    if (args.coords is None) == (args.file is None):
        parser.error("give the coordinates either as a JSON string or with --file")
    if args.radio_range < 0:
        parser.error("--range cannot be negative")
    try:
        coords = parse_coords(args.coords if args.file is None else args.file.read_text())
    except (OSError, ValueError) as error:
        parser.error(f"invalid coordinates: {error}")

    physical = build_physical_graph(coords, args.radio_range)
    conflict = build_conflict_graph(physical)
    schedules = {name: assign_slots(conflict, name) for name in STRATEGIES}
    # min() keeps the first strategy on a tie, so DSATUR wins ties.
    chosen = min(schedules, key=lambda name: frame_length(schedules[name]))
    slots = schedules[chosen]

    collisions = find_collisions(coords, slots, args.radio_range)
    if collisions:
        for a, b, reason in collisions:
            print(f"COLLISION: {a} and {b} share slot {slots[a]}: {reason}", file=sys.stderr)
        return 1

    comparison = {name: frame_length(schedule) for name, schedule in schedules.items()}
    print(format_report(slots, args.radio_range, comparison, chosen, slot_lower_bound(physical)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
