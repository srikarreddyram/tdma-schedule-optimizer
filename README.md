# TDMA Schedule Optimizer

A Python CLI that assigns TDMA time slots to a network of radios so that no two
radios that can interfere with each other ever transmit in the same slot, while
reusing slots wherever the topology allows.

It was built for the Vaan Megam Networks wireless protocol development task:

- **Part 1** (`src/`): the Python scheduling engine and CLI.
- **Part 2** (`emane/`): a bridge that loads the schedule into an EMANE
  emulation of 16 TDMA radios, and a demo that measures packet delivery.

The design process, reasoning and final values are in
[docs/documentation.pdf](docs/documentation.pdf); the slides are in
[presentation.pptx](presentation.pptx).

## Setup

Requires Python 3.10 or newer.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

Pass the node coordinates as a JSON string, or point at a JSON file:

```
.venv/bin/python src/cli.py '{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0],"Node_03":[600.0,0.0]}'
.venv/bin/python src/cli.py --file data/grid16.json
.venv/bin/python src/cli.py --file data/grid16.json --range 350
```

`--range` is the radio range in meters (default 500.0). The tool works for any
number of nodes, not only 16.

The report lists the frame length, the node-to-slot mapping and the slot × node
matrix (`1` means that node transmits in that slot). If the self-check finds a
collision, the tool prints the offending pairs and exits with status 1 instead
of printing a schedule.

## How it works

1. **Physical graph.** Each radio is a node. Two radios are linked if they are
   at most `--range` meters apart.
2. **Conflict graph.** Two radios conflict if they are 1 hop apart (direct
   interference) or 2 hops apart (hidden terminal: both would collide at their
   common neighbour). This is the square of the physical graph, built with
   `networkx.power(G, 2)`.
3. **Slot assignment.** The conflict graph is coloured greedily, and each colour
   is one time slot. Two orderings are run and the shorter schedule is kept:
   - `DSATUR`: always colour next the node whose neighbours already use the
     most different colours.
   - `largest_first`: colour nodes in order of decreasing number of conflicts.

   Both are written out in `graph_engine.py` (`dsatur`, `largest_first`), and
   the tests check that they produce exactly the same colourings as
   networkx's built-in `greedy_color`.
4. **Lower bound.** A radio and all of its neighbours are pairwise within 2
   hops, so they all need different slots. The busiest radio's neighbour count
   plus one is therefore a floor on the frame length. When the schedule reaches
   that floor, the report marks it as optimal.
5. **Self-check.** Before anything is printed, `validator.py` recomputes the
   interference rules from the raw coordinates, without using the conflict
   graph, and confirms that no two radios sharing a slot are within 2 hops.

## Result on the 16-node test set

The task gives the first two coordinates and the last one
(`[0,0]`, `[300,0]`, …, `[900,900]`). `data/grid16.json` assumes these describe
a 4 × 4 grid with 300 m spacing, numbered row by row.

On that grid the tool produces a 9-slot frame, which is the minimum possible.
Each radio reaches its horizontal, vertical and diagonal neighbours (300 m and
about 424 m), so an interior radio has 8 neighbours, and those 9 radios must all
use different slots.

The sample output in the task statement shows 5 slots. Applied to this grid,
that sample assignment only separates direct neighbours: for example Node_01
and Node_03 share slot 0 although both reach Node_02. A test in
`tests/test_scheduler.py` confirms the validator flags it.

## Tests

```
.venv/bin/python -m pytest
```

The tests cover a fully disconnected network (everyone in slot 0), a fully
connected one (one slot per node), the A–B–C hidden-terminal line, slot reuse
beyond 2 hops on a longer line, the 16-node grid, 20 random layouts per
strategy, DSATUR on small textbook graphs, the hand-written colouring
against networkx's, the validator itself, CLI input handling, and the EMANE
bridge.

## Part 2: EMANE emulation

Requires Docker. The image compiles EMANE 1.5.3 from source, so the first build
is slow.

```
docker build -t tdma-emane -f emane/Dockerfile .
docker run --rm --privileged -v "$PWD/emane/out:/work/emane/out" tdma-emane
```

The container needs `--privileged` because it creates network namespaces and
TUN devices. `emane/run_demo.sh` then:

1. creates one network namespace per radio, joined by a bridge, and starts one
   EMANE instance (one TDMA radio) in each;
2. publishes pathloss so that radios hear each other only within 500 m
   (`pathloss.py`);
3. converts the Part 1 schedule into EMANE's TDMA schedule XML (`bridge.py`)
   and sends it with `emaneevent-tdmaschedule`;
4. has all radios broadcast at once (`traffic.py`) and reports the share of
   packets that crossed each in-range link, plus EMANE's own drop reasons
   (`report.py`).

Each run tests two schedules, the optimizer's 9-slot schedule and a 5-slot
control that only separates direct neighbours, at two slot durations (1 ms and
10 ms). Results are written to `emane/out/`. In the recorded run:

| Schedule | Slot | Packets delivered | SINR (collision) drops |
|---|---|---|---|
| Optimizer, 9 slots | 1 ms | 83.4% | none |
| Distance-1 control, 5 slots | 1 ms | 65.2% | 274,992 bytes |
| Optimizer, 9 slots | 10 ms | 99.9% | none |
| Distance-1 control, 5 slots | 10 ms | 34.5% | 763,194 bytes |

The optimizer's schedule never produced a collision drop. Its loss with 1 ms
slots is emulator timing in a virtual machine (packets arriving after their
slot has ended) and varied between 83.4% and 99.4% delivery over three runs;
see section 6 of the documentation.

Environment variables for `docker run -e`: `PACKETS` (packets per radio,
default 300) and `SLOT_DURATIONS_US` (default `"1000 10000"`).

## Layout

```
src/graph_engine.py     graph construction, conflict graph, colouring, lower bound
src/validator.py        independent collision check
src/formatter.py        text report
src/cli.py              command-line entry point
data/grid16.json        16-node test set
tests/                  pytest suite
emane/Dockerfile        EMANE + this project in one container
emane/xml/              EMANE TDMA radio configuration
emane/bridge.py         Part 1 schedule -> EMANE schedule XML
emane/pathloss.py       radio range -> EMANE pathloss events
emane/traffic.py        broadcast probe run in each radio's namespace
emane/report.py         delivery and drop summary
emane/run_demo.sh       runs the whole emulation
emane/out/              recorded results
docs/documentation.pdf  project documentation
docs/build/             script that generates the PDF
presentation.pptx       slides
```
