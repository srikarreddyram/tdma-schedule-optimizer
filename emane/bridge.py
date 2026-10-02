"""Bridge: turn a Part 1 schedule into an EMANE TDMA schedule XML.

EMANE identifies radios by integer NEM id, so node names are numbered 1..N in
input order. Each colour (slot) from Part 1 becomes one slot of a single
recurring frame, and the nodes holding that colour are its transmitters. EMANE
treats every slot a NEM does not transmit in as a receive slot.

Usage:
    python3 emane/bridge.py --file data/grid16.json --out schedule.xml
    python3 emane/bridge.py --file data/grid16.json --slots other.json --out other.xml
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cli import parse_coords
from graph_engine import (
    DEFAULT_RANGE_M,
    STRATEGIES,
    assign_slots,
    build_conflict_graph,
    build_physical_graph,
    frame_length,
)

# Radio settings shared by every slot of the schedule.
SLOT_DURATION_US = 1000  # 1 ms slots, as the task asks; override with --slot-us
SLOT_OVERHEAD_US = 0
BANDWIDTH = "1M"
FREQUENCY = "2.4G"
DATARATE = "11M"
TX_POWER_DBM = 20


def optimise(coords, radio_range=DEFAULT_RANGE_M):
    """Run the Part 1 engine and return the shortest node -> slot schedule."""
    conflict = build_conflict_graph(build_physical_graph(coords, radio_range))
    return min((assign_slots(conflict, name) for name in STRATEGIES), key=frame_length)


def nem_ids(nodes):
    return {node: index for index, node in enumerate(nodes, start=1)}


def schedule_xml(slots, slot_us=SLOT_DURATION_US):
    """Return the <emane-tdma-schedule> document for a node -> slot mapping."""
    ids = nem_ids(slots)
    frame = frame_length(slots)
    root = ET.Element("emane-tdma-schedule")
    ET.SubElement(root, "structure", frames="1", slots=str(frame),
                  slotoverhead=str(SLOT_OVERHEAD_US), slotduration=str(slot_us),
                  bandwidth=BANDWIDTH)
    multiframe = ET.SubElement(root, "multiframe", frequency=FREQUENCY,
                               power=str(TX_POWER_DBM), datarate=DATARATE)
    multiframe.set("class", "0")
    frame_element = ET.SubElement(multiframe, "frame", index="0")
    for slot in range(frame):
        transmitters = [str(ids[node]) for node in slots if slots[node] == slot]
        slot_element = ET.SubElement(frame_element, "slot", index=str(slot),
                                     nodes=",".join(transmitters))
        ET.SubElement(slot_element, "tx")
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--file", type=Path, required=True, help="JSON node coordinates")
    parser.add_argument("--range", type=float, default=DEFAULT_RANGE_M, dest="radio_range")
    parser.add_argument("--slots", type=Path,
                        help="JSON node -> slot mapping to convert instead of running the optimizer")
    parser.add_argument("--slot-us", type=int, default=SLOT_DURATION_US,
                        help="slot duration in microseconds (default: %(default)s)")
    parser.add_argument("--out", type=Path, required=True, help="where to write the schedule XML")
    args = parser.parse_args(argv)

    coords = parse_coords(args.file.read_text())
    if args.slots is None:
        slots = optimise(coords, args.radio_range)
    else:
        given = json.loads(args.slots.read_text())
        slots = {node: given[node] for node in coords}
    args.out.write_text(schedule_xml(slots, args.slot_us))
    print(f"{args.out}: {len(slots)} NEMs, {frame_length(slots)} slots of {args.slot_us} us per frame")
    return 0


if __name__ == "__main__":
    sys.exit(main())
