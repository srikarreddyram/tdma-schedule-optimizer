import json
import random
from pathlib import Path

import pytest

import cli
import networkx as nx

from graph_engine import (
    STRATEGIES,
    assign_slots,
    build_conflict_graph,
    build_physical_graph,
    frame_length,
    slot_lower_bound,
)
from validator import find_collisions

RANGE = 500.0
GRID16_FILE = Path(__file__).parent.parent / "data" / "grid16.json"
GRID16 = cli.parse_coords(GRID16_FILE.read_text())


def schedule(coords, strategy="DSATUR", radio_range=RANGE):
    conflict = build_conflict_graph(build_physical_graph(coords, radio_range))
    return assign_slots(conflict, strategy)


def line(count, spacing=400.0):
    return {f"N{i}": (i * spacing, 0.0) for i in range(count)}


def test_disconnected_nodes_all_reuse_slot_0():
    coords = {f"N{i}": (i * 2000.0, 0.0) for i in range(6)}
    assert set(schedule(coords).values()) == {0}


def test_fully_connected_needs_one_slot_per_node():
    coords = {f"N{i}": (i * 10.0, 0.0) for i in range(6)}
    assert frame_length(schedule(coords)) == 6


def test_hidden_terminal_gets_different_slots():
    # A - B - C: A and C are out of range of each other but both reach B.
    slots = schedule(line(3))
    assert len(set(slots.values())) == 3


def test_line_reuses_slots_beyond_two_hops():
    slots = schedule(line(9))
    assert frame_length(slots) == 3
    assert slots["N0"] == slots["N3"] == slots["N6"]


def test_range_boundary_is_inclusive():
    coords = {"A": (0.0, 0.0), "B": (500.0, 0.0)}
    assert build_physical_graph(coords, RANGE).has_edge("A", "B")


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_grid16_is_conflict_free_and_optimal(strategy):
    slots = schedule(GRID16, strategy)
    assert find_collisions(GRID16, slots, RANGE) == []
    assert frame_length(slots) == slot_lower_bound(build_physical_graph(GRID16, RANGE)) == 9


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("seed", range(20))
def test_random_topologies_are_conflict_free(strategy, seed):
    rng = random.Random(seed)
    coords = {f"N{i}": (rng.uniform(0, 2000), rng.uniform(0, 2000)) for i in range(rng.randint(1, 40))}
    slots = schedule(coords, strategy)
    assert find_collisions(coords, slots, RANGE) == []
    assert frame_length(slots) >= slot_lower_bound(build_physical_graph(coords, RANGE))


def test_validator_catches_direct_and_hidden_terminal_collisions():
    coords = line(3)
    assert find_collisions(coords, {"N0": 0, "N1": 0, "N2": 1}, RANGE) == [("N0", "N1", "direct link (1-hop)")]
    assert find_collisions(coords, {"N0": 0, "N1": 1, "N2": 0}, RANGE) == [
        ("N0", "N2", "hidden terminal (2-hop) at N1")
    ]


def test_task_pdf_sample_schedule_collides_on_grid16():
    # The 5-slot sample in the task PDF only separates direct neighbours.
    sample = [0, 1, 0, 1, 2, 3, 2, 3, 0, 1, 4, 1, 2, 3, 2, 3]
    slots = dict(zip(GRID16, sample))
    reasons = {reason.split(" at ")[0] for _, _, reason in find_collisions(GRID16, slots, RANGE)}
    assert reasons == {"hidden terminal (2-hop)"}


def test_cli_prints_report(capsys):
    assert cli.main([json.dumps({name: list(xy) for name, xy in GRID16.items()})]) == 0
    out = capsys.readouterr().out
    assert "Optimized Frame Length : 9 unique timeslots" in out
    assert " Node_01: Slot 0" in out
    assert "Slot 08     |" in out
    assert "Schedule verified conflict-free." in out


def test_cli_range_flag_changes_schedule(capsys):
    assert cli.main(["--file", str(GRID16_FILE), "--range", "100"]) == 0
    assert "Optimized Frame Length : 1 unique timeslots" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["not json", "[]", "{}", '{"A": [1]}', '{"A": ["x", 2]}'])
def test_cli_rejects_bad_input(bad):
    with pytest.raises(SystemExit):
        cli.main([bad])


def test_bridge_schedule_xml_matches_schedule():
    import sys
    import xml.etree.ElementTree as ET

    sys.path.insert(0, str(GRID16_FILE.parent.parent / "emane"))
    import bridge

    slots = bridge.optimise(GRID16)
    root = ET.fromstring(bridge.schedule_xml(slots))
    assert root.find("structure").attrib["slots"] == "9"
    assert root.find("structure").attrib["slotduration"] == "1000"
    nodes = list(GRID16)
    transmitters = {
        int(slot.attrib["index"]): {nodes[int(nem) - 1] for nem in slot.attrib["nodes"].split(",")}
        for slot in root.iter("slot")
    }
    assert transmitters == {
        index: {node for node in nodes if slots[node] == index} for index in range(9)
    }


def test_dsatur_colours_odd_cycle_with_three_and_even_cycle_with_two():
    assert len(set(STRATEGIES["DSATUR"](nx.cycle_graph(5)).values())) == 3
    assert len(set(STRATEGIES["DSATUR"](nx.cycle_graph(6)).values())) == 2


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("seed", range(20))
def test_hand_written_colouring_matches_networkx(strategy, seed):
    rng = random.Random(seed)
    coords = {f"N{i}": (rng.uniform(0, 2000), rng.uniform(0, 2000)) for i in range(30)}
    conflict = build_conflict_graph(build_physical_graph(coords, RANGE))
    assert STRATEGIES[strategy](conflict) == nx.greedy_color(conflict, strategy=strategy)
