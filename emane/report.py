"""Summarise one traffic run: what fraction of packets crossed each radio link.

Usage: python3 emane/report.py --file data/grid16.json --run emane/out/optimised
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cli import parse_coords
from graph_engine import DEFAULT_RANGE_M


def summarise(coords, radio_range, tallies):
    """tallies maps a NEM id to that radio's traffic.py output."""
    nodes = list(coords)
    nem = {node: index for index, node in enumerate(nodes, start=1)}
    links = sent = delivered = lossy_links = leaked = 0
    per_receiver = {}
    for receiver in nodes:
        heard = tallies[nem[receiver]]["heard"]
        expected = got = 0
        for sender in nodes:
            if sender == receiver:
                continue
            count = heard.get(str(nem[sender]), 0)
            if math.dist(coords[sender], coords[receiver]) <= radio_range:
                packets = tallies[nem[sender]]["sent"]
                links += 1
                expected += packets
                got += count
                lossy_links += count < packets
            else:
                leaked += count
        per_receiver[receiver] = round(100.0 * got / expected, 1) if expected else None
        sent += expected
        delivered += got
    return {
        "links": links,
        "sent": sent,
        "delivered": delivered,
        "delivery_percent": round(100.0 * delivered / sent, 1) if sent else None,
        "lossy_links": lossy_links,
        "out_of_range_packets": leaked,
        "per_receiver_percent": per_receiver,
    }


def drop_reasons(run):
    """Sum the bytes each radio's TDMA MAC dropped, per reason, from its emanesh drop table."""
    totals = {}
    for path in run.glob("drops*.txt"):
        header = None
        for line in path.read_text().splitlines():
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if header is None:
                header = cells
                continue
            for reason, value in zip(header[1:], cells[1:]):
                totals[reason] = totals.get(reason, 0) + int(value)
    return {reason: total for reason, total in totals.items() if total}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--file", type=Path, required=True, help="JSON node coordinates")
    parser.add_argument("--range", type=float, default=DEFAULT_RANGE_M, dest="radio_range")
    parser.add_argument("--run", type=Path, required=True, help="directory of node*.json tallies")
    args = parser.parse_args(argv)

    coords = parse_coords(args.file.read_text())
    tallies = {}
    for path in args.run.glob("node*.json"):
        tally = json.loads(path.read_text())
        tallies[tally["nem"]] = tally
    summary = summarise(coords, args.radio_range, tallies)
    summary["mac_bytes_dropped_by_reason"] = drop_reasons(args.run)
    (args.run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(f"In-range links        : {summary['links']}")
    print(f"Packets delivered     : {summary['delivered']} / {summary['sent']}"
          f" ({summary['delivery_percent']}%)")
    print(f"Links with any loss   : {summary['lossy_links']}")
    print(f"Out-of-range packets  : {summary['out_of_range_packets']}")
    print(f"MAC drops (bytes)     : {summary['mac_bytes_dropped_by_reason'] or 'none'}")
    print("Delivery per receiver :")
    for node, percent in summary["per_receiver_percent"].items():
        print(f"  {node}: {percent}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
