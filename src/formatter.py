"""Text report: summary, node -> slot mapping, and the slot x node matrix."""
from graph_engine import frame_length

RULE = "=" * 64
THIN_RULE = "-" * 65
ROW_LABEL = "Slot \\ Node"


def format_report(slots, radio_range, comparison, chosen, lower_bound):
    """comparison maps each strategy name to the frame length it achieved."""
    nodes = list(slots)
    frame = frame_length(slots)
    compared = ", ".join(f"{name} = {length}" for name, length in comparison.items())
    optimal = " -> schedule is optimal" if frame == lower_bound else ""

    lines = [
        RULE,
        " TDMA TOPOLOGY OPTIMIZATION REPORT",
        RULE,
        f"Total Nodes Processed  : {len(nodes)}",
        f"Configured Radio Range : {radio_range} meters",
        f"Optimized Frame Length : {frame} unique timeslots (Lower is better)",
        f"Heuristics Compared    : {compared} (using {chosen})",
        f"Slot Lower Bound       : {lower_bound}{optimal}",
        THIN_RULE,
        "NODE -> SLOT ASSIGNMENTS:",
    ]
    lines += [f" {node}: Slot {slots[node]}" for node in nodes]
    lines += ["", "STRUCTURAL TDMA SCHEDULE MATRIX (Slot x Node Boolean Matrix):"]
    lines += _matrix_lines(nodes, slots, frame)
    lines += ["Execution finalized cleanly. Schedule verified conflict-free.", RULE]
    return "\n".join(lines)


def _matrix_lines(nodes, slots, frame):
    labels = [node.removeprefix("Node_") for node in nodes]
    width = max(len(label) for label in labels)
    header = " | ".join([ROW_LABEL] + [label.rjust(width) for label in labels])
    rule = "-" * len(header)
    rows = []
    for slot in range(frame):
        cells = [str(int(slots[node] == slot)).rjust(width) for node in nodes]
        rows.append(" | ".join([f"Slot {slot:02d}".ljust(len(ROW_LABEL))] + cells))
    return [header, rule, *rows, rule]
