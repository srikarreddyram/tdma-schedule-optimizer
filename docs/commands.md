# Commands

All commands are run from the project folder:

```
cd "/Users/tejsr/Projects/Schedule Optimizer"
```

## One-time setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Python 3.10 or newer is required. The virtual environment already exists on this machine, so skip this unless starting from a fresh clone.

## Part 1: the scheduler

### 16-node grid (the main case)

```
.venv/bin/python src/cli.py --file data/grid16.json
```

Expected: 9 slots, lower bound 9, "schedule is optimal".

### Coordinates as a JSON string (the task's input format)

```
.venv/bin/python src/cli.py '{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0],"Node_03":[600.0,0.0],"Node_04":[900.0,0.0],"Node_05":[0.0,300.0],"Node_06":[300.0,300.0],"Node_07":[600.0,300.0],"Node_08":[900.0,300.0],"Node_09":[0.0,600.0],"Node_10":[300.0,600.0],"Node_11":[600.0,600.0],"Node_12":[900.0,600.0],"Node_13":[0.0,900.0],"Node_14":[300.0,900.0],"Node_15":[600.0,900.0],"Node_16":[900.0,900.0]}'
```

Same result as the file version.

### 5-radio line (hidden terminal and slot reuse)

```
.venv/bin/python src/cli.py '{"A":[0,0],"B":[400,0],"C":[800,0],"D":[1200,0],"E":[1600,0]}'
```

Expected: 3 slots, A0 B1 C2 D0 E1. A and D share a slot because they are 3 hops apart.

### Changing the radio range

The default range is 500 m (`DEFAULT_RANGE_M` in `src/graph_engine.py`). Override it with `--range`, in metres.

```
.venv/bin/python src/cli.py --file data/grid16.json --range 350
.venv/bin/python src/cli.py --file data/grid16.json --range 300
.venv/bin/python src/cli.py --file data/grid16.json --range 299
.venv/bin/python src/cli.py --file data/grid16.json --range 2000
```

| `--range` | Frame length | Why |
|---|---|---|
| 500 (default) | 9 | Diagonal links (about 424 m) are in range |
| 350 | 5 | Only horizontal and vertical links (300 m) are in range |
| 300 | 5 | Exactly 300 m counts as in range, so the same links as 350 |
| 299 | 1 | Nobody is in range, so every radio reuses slot 0 |
| 2000 | 16 | Everybody is in range, so one slot per radio |

The grid's 300 m is the spacing between radios and is fixed in `data/grid16.json`. The range is separate: it decides which pairs count as linked.

### Invalid input is rejected

```
.venv/bin/python src/cli.py '{"A":[0]}'
.venv/bin/python src/cli.py 'not json'
.venv/bin/python src/cli.py --file data/grid16.json --range -5
```

Each prints a clear error and exits without a traceback.

### Validator on the task's 5-slot sample

```
.venv/bin/python -c "
import sys, json; sys.path.insert(0,'src')
from cli import parse_coords; from validator import find_collisions
c = parse_coords(open('data/grid16.json').read()); s = json.load(open('emane/distance1_schedule.json'))
r = find_collisions(c, s, 500.0); print(len(r), 'collisions; first:', r[0])"
```

Expected: 21 collisions, all hidden-terminal. The sample assignment separates direct neighbours only.

### Tests

```
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -v
```

Expected: 98 passed. `-v` lists every test by name.

## Part 2: EMANE emulation

Docker is provided by Colima on this machine.

```
colima start
```

Full emulation: four schedules (optimizer and control, each at 1 ms and 10 ms slots). It takes a few minutes.

```
docker run --rm --privileged tdma-emane
```

Faster run (10 ms slots only, fewer packets):

```
docker run --rm --privileged -e PACKETS=100 -e SLOT_DURATIONS_US=10000 tdma-emane
```

Do not add `-v "$PWD/emane/out:/work/emane/out"` unless the recorded results should be overwritten.

When finished:

```
colima stop
```

### Building the image (only if it is missing)

```
docker build -t tdma-emane -f emane/Dockerfile .
```

The first build compiles EMANE from source and is slow. Check whether the image exists with `docker images tdma-emane`.

### Reading the output

| Line | Meaning |
|---|---|
| `scheduler.scheduleAcceptFull` | The radio accepted the schedule it was sent |
| `ScheduleInfoTable` | One TX slot and RX in all others, as written by the bridge |
| `Packets delivered` | Packets that arrived over the in-range links |
| `MAC drops (bytes)` | `SINR` means lost to interference; `Slot Error` and `Long` are timing |
| `Out-of-range packets` | Must be 0; the 500 m range held |

The optimizer's schedule shows no `SINR` drops in any run. Delivery percentages at 1 ms slots vary from run to run because of emulator timing.

### Recorded results (fallback)

```
emane/out/demo_log.txt
emane/out/optimised_10000us/summary.json
emane/out/distance1_10000us/summary.json
```

## Individual EMANE tools

Convert a schedule to EMANE's schedule XML:

```
.venv/bin/python emane/bridge.py --file data/grid16.json --out /tmp/schedule.xml
.venv/bin/python emane/bridge.py --file data/grid16.json --slot-us 10000 --out /tmp/schedule_10ms.xml
.venv/bin/python emane/bridge.py --file data/grid16.json --slots emane/distance1_schedule.json --out /tmp/control.xml
```
