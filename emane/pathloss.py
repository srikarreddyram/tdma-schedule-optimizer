"""Tell EMANE which radios can hear each other.

Part 1 assumes a radio hears everything within the radio range and nothing
beyond it. EMANE has no "range" setting, so the same rule is expressed as
pathloss: pairs within range get the free-space loss for their distance, and
pairs beyond it get a loss so large that the signal is below the receiver's
sensitivity and is discarded.

Usage: python3 emane/pathloss.py --file data/grid16.json --device emanebr
"""
import argparse
import math
import sys
from pathlib import Path

from emane.events import EventService, PathlossEvent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cli import parse_coords
from graph_engine import DEFAULT_RANGE_M

EVENT_GROUP = "224.1.2.8"
EVENT_PORT = 45703
FREQUENCY_HZ = 2.4e9
OUT_OF_RANGE_DB = 300.0


def free_space_loss_db(distance_m, frequency_hz=FREQUENCY_HZ):
    return 20 * math.log10(distance_m) + 20 * math.log10(frequency_hz) - 147.55


def pathloss_db(a, b, radio_range):
    distance = math.dist(a, b)
    if distance > radio_range:
        return OUT_OF_RANGE_DB
    return free_space_loss_db(max(distance, 1.0))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--file", type=Path, required=True, help="JSON node coordinates")
    parser.add_argument("--range", type=float, default=DEFAULT_RANGE_M, dest="radio_range")
    parser.add_argument("--device", required=True, help="interface on the EMANE event channel")
    args = parser.parse_args(argv)

    coords = parse_coords(args.file.read_text())
    nem = {node: index for index, node in enumerate(coords, start=1)}
    service = EventService((EVENT_GROUP, EVENT_PORT, args.device))
    for receiver in coords:
        event = PathlossEvent()
        for sender in coords:
            if sender != receiver:
                event.append(nem[sender],
                             forward=pathloss_db(coords[sender], coords[receiver], args.radio_range))
        service.publish(nem[receiver], event)
    print(f"pathloss published for {len(coords)} NEMs (range {args.radio_range} m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
