"""Vector figures for the documentation PDF, drawn from the project's own data."""
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor

INK = HexColor("#0b0b0b")
SECONDARY = HexColor("#52514e")
MUTED = HexColor("#898781")
HAIRLINE = HexColor("#c3c2b7")
SURFACE = HexColor("#ffffff")
BLUE = HexColor("#2a78d6")
NEUTRAL_FILL = HexColor("#e1e0d9")
PANEL = HexColor("#f4f4f2")
# One-hue ramp (light -> dark) used for delivery percentages.
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
FONT, BOLD = "Helvetica", "Helvetica-Bold"


def _grid_positions(coords, size, pad):
    """Map coordinates into the drawing, first node at the top-left."""
    xs = [x for x, _ in coords.values()]
    ys = [y for _, y in coords.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    scale = (size - 2 * pad) / span
    return {node: (pad + (x - min(xs)) * scale, size - pad - (y - min(ys)) * scale)
            for node, (x, y) in coords.items()}


def topology(coords, graph, slots, size=230):
    """Radios and links, each radio labelled with its slot."""
    legend_height = 34
    drawing = Drawing(size, size + legend_height)
    position = {node: (x, y + legend_height)
                for node, (x, y) in _grid_positions(coords, size, pad=26).items()}
    for a, b in graph.edges:
        drawing.add(Line(*position[a], *position[b], strokeColor=HAIRLINE, strokeWidth=0.8))
    users = {}
    for node, slot in slots.items():
        users[slot] = users.get(slot, 0) + 1
    for node, (x, y) in position.items():
        shared = users[slots[node]] > 1
        drawing.add(Circle(x, y, 12, fillColor=BLUE if shared else NEUTRAL_FILL,
                           strokeColor=SURFACE, strokeWidth=2))
        drawing.add(String(x, y - 3.4, str(slots[node]), fontName=BOLD, fontSize=10,
                           textAnchor="middle", fillColor=SURFACE if shared else INK))
        drawing.add(String(x + 13, y + 9, node.removeprefix("Node_"), fontName=FONT,
                           fontSize=6.5, fillColor=MUTED))
    for row, (fill, text) in enumerate([(BLUE, "slot shared with another radio (spatial reuse)"),
                                        (NEUTRAL_FILL, "slot used by this radio only")]):
        y = 20 - row * 14
        drawing.add(Circle(8, y, 5, fillColor=fill, strokeColor=None))
        drawing.add(String(18, y - 3, text, fontName=FONT, fontSize=8, fillColor=SECONDARY))
    return drawing


def delivery_heatmap(coords, percent_by_node, title, size=190):
    """One cell per radio, shaded by the share of neighbour packets it received."""
    title_height = 18
    drawing = Drawing(size, size + title_height)
    drawing.add(String(0, size + 5, title, fontName=BOLD, fontSize=9, fillColor=INK))
    side = int(round(len(coords) ** 0.5))
    cell = size / side
    position = _grid_positions(coords, size, pad=cell / 2)
    for node, (x, y) in position.items():
        percent = percent_by_node[node]
        step = min(int(percent / 100 * len(BLUE_RAMP)), len(BLUE_RAMP) - 1)
        drawing.add(Rect(x - cell / 2 + 1, y - cell / 2 + 1, cell - 2, cell - 2,
                         fillColor=HexColor(BLUE_RAMP[step]), strokeColor=None, rx=3, ry=3))
        ink = SURFACE if step >= 3 else INK
        drawing.add(String(x, y - 1, f"{percent:g}%", fontName=BOLD, fontSize=10,
                           textAnchor="middle", fillColor=ink))
        drawing.add(String(x, y - 12, node.removeprefix("Node_"), fontName=FONT, fontSize=6.5,
                           textAnchor="middle", fillColor=ink))
    return drawing


def _box(drawing, x, y, w, h, lines, fill=SURFACE, bold_first=True, size=7.5):
    drawing.add(Rect(x, y, w, h, fillColor=fill, strokeColor=HAIRLINE, strokeWidth=0.8, rx=4, ry=4))
    top = y + h - 11
    for index, line in enumerate(lines):
        drawing.add(String(x + w / 2, top - index * 10, line,
                           fontName=BOLD if bold_first and index == 0 else FONT,
                           fontSize=size, textAnchor="middle",
                           fillColor=INK if index == 0 else SECONDARY))


def _arrow(drawing, x1, y1, x2, y2):
    drawing.add(Line(x1, y1, x2, y2, strokeColor=SECONDARY, strokeWidth=1))
    drawing.add(Line(x2, y2, x2 - 4, y2 + 5, strokeColor=SECONDARY, strokeWidth=1))
    drawing.add(Line(x2, y2, x2 + 4, y2 + 5, strokeColor=SECONDARY, strokeWidth=1))


def architecture(width=470):
    """How the Part 1 schedule reaches the EMANE radios inside one container."""
    height = 232
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=PANEL, strokeColor=None, rx=6, ry=6))
    drawing.add(String(10, height - 14, "One Docker container (privileged)", fontName=BOLD,
                       fontSize=8, fillColor=SECONDARY))

    third = (width - 40) / 3
    tops = height - 68
    _box(drawing, 10, tops, third, 44, ["Part 1 optimizer", "coordinates -> node/slot map"])
    _box(drawing, 20 + third, tops, third, 44, ["bridge.py", "node/slot map -> schedule XML"])
    _box(drawing, 30 + 2 * third, tops, third, 44, ["pathloss.py", "500 m range -> pathloss"])
    drawing.add(Line(10 + third, tops + 22, 20 + third, tops + 22, strokeColor=SECONDARY, strokeWidth=1))

    bus_y = height - 112
    drawing.add(Rect(10, bus_y, width - 20, 22, fillColor=BLUE, strokeColor=None, rx=4, ry=4))
    drawing.add(String(width / 2, bus_y + 7,
                       "Linux bridge emanebr: EMANE event channel + over-the-air channel (multicast)",
                       fontName=BOLD, fontSize=7.5, textAnchor="middle", fillColor=SURFACE))
    _arrow(drawing, 20 + 1.5 * third, tops, 20 + 1.5 * third, bus_y + 22)
    _arrow(drawing, 30 + 2.5 * third, tops, 30 + 2.5 * third, bus_y + 22)

    labels = ["namespace node1", "namespace node2", "...", "namespace node16"]
    box_w = (width - 50) / 4
    for index, label in enumerate(labels):
        x = 10 + index * (box_w + 10)
        if label == "...":
            drawing.add(String(x + box_w / 2, 50, "...", fontName=BOLD, fontSize=14,
                               textAnchor="middle", fillColor=MUTED))
            continue
        nem = label.removeprefix("namespace node")
        _box(drawing, x, 10, box_w, 84,
             [label, f"emane: TDMA NEM {nem}", f"emane0 10.100.0.{nem}", "traffic.py probe",
              "", "veth -> emanebr"])
        _arrow(drawing, x + box_w / 2, bus_y, x + box_w / 2, 94)
    return drawing
