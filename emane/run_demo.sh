#!/bin/bash
# End-to-end EMANE demo. Runs inside the container, which must be started with
# --privileged (network namespaces and TUN devices):
#
#   docker build -t tdma-emane -f emane/Dockerfile .
#   docker run --rm --privileged -v "$PWD/emane/out:/work/emane/out" tdma-emane
#
# For each schedule it loads the schedule into every radio, has all radios
# broadcast at once, and reports how many packets crossed each in-range link.
set -euo pipefail
cd /work

COORDS=${COORDS:-data/grid16.json}
PACKETS=${PACKETS:-300}
SLOT_DURATIONS_US=${SLOT_DURATIONS_US:-"1000 10000"}
OUT=emane/out
RUN=/tmp/emane-run
BRIDGE_DEV=emanebr
NODES=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$COORDS")

mkdir -p "$OUT" "$RUN"
cp emane/xml/*.xml "$RUN"/
mkdir -p /dev/net
[ -c /dev/net/tun ] || mknod /dev/net/tun c 10 200

echo "== 1. One network namespace per radio, joined by a bridge =="
# The bridge carries EMANE's over-the-air and event multicast traffic.
ip link add "$BRIDGE_DEV" type bridge
echo 0 > "/sys/class/net/$BRIDGE_DEV/bridge/multicast_snooping"
ip addr add 10.99.0.254/24 dev "$BRIDGE_DEV"
ip link set "$BRIDGE_DEV" up
for i in $(seq 1 "$NODES"); do
    ip netns add "node$i"
    ip link add "veth$i" type veth peer name ota0 netns "node$i"
    ip link set "veth$i" master "$BRIDGE_DEV" up
    ip -n "node$i" link set lo up
    ip -n "node$i" addr add "10.99.0.$i/24" dev ota0
    ip -n "node$i" link set ota0 up
done

echo "== 2. One EMANE instance (one TDMA radio) per namespace =="
for i in $(seq 1 "$NODES"); do
    cat > "$RUN/platform$i.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE platform SYSTEM "file:///usr/share/emane/dtd/platform.dtd">
<platform>
  <param name="otamanagerchannelenable" value="on"/>
  <param name="otamanagerdevice" value="ota0"/>
  <param name="otamanagergroup" value="224.1.2.8:45702"/>
  <param name="eventservicedevice" value="ota0"/>
  <param name="eventservicegroup" value="224.1.2.8:45703"/>
  <param name="controlportendpoint" value="0.0.0.0:47000"/>
  <nem id="$i" definition="tdmanem.xml">
    <transport definition="transvirtual.xml">
      <param name="address" value="10.100.0.$i"/>
      <param name="mask" value="255.255.255.0"/>
    </transport>
  </nem>
</platform>
EOF
    (cd "$RUN" && ip netns exec "node$i" emane "platform$i.xml" -r -d -l 2 -f "$RUN/emane$i.log")
done
sleep 3

echo "== 3. Radio range as pathloss =="
python3 emane/pathloss.py --file "$COORDS" --device "$BRIDGE_DEV"

run_schedule() {
    local name=$1 xml=$2
    echo
    echo "== Schedule: $name =="
    emaneevent-tdmaschedule "$xml" -i "$BRIDGE_DEV"
    sleep 2
    ip netns exec node1 emanesh localhost get stat 1 mac scheduler.scheduleAcceptFull
    ip netns exec node1 emanesh localhost get table 1 mac scheduler.ScheduleInfoTable

    mkdir -p "$OUT/$name"
    rm -f "$OUT/$name"/node*.json "$OUT/$name"/drops*.txt
    cp "$xml" "$OUT/$name/schedule.xml"
    for i in $(seq 1 "$NODES"); do
        ip netns exec "node$i" emanesh localhost clear table "$i" mac > /dev/null
    done
    local start=$(( $(date +%s) + 3 ))
    for i in $(seq 1 "$NODES"); do
        ip netns exec "node$i" python3 emane/traffic.py --nem "$i" --count "$PACKETS" \
            --start "$start" --out "$OUT/$name/node$i.json" &
    done
    wait
    # EMANE's own account of why each radio discarded what it discarded.
    for i in $(seq 1 "$NODES"); do
        ip netns exec "node$i" emanesh localhost get table "$i" mac BroadcastByteDropTable0 \
            > "$OUT/$name/drops$i.txt"
    done
    python3 emane/report.py --file "$COORDS" --run "$OUT/$name"
}

echo "== 4. Bridge: Part 1 schedule -> EMANE schedule XML =="
# Each slot duration is run twice: with the optimizer's distance-2 schedule, and
# with a control that only separates direct neighbours and therefore leaves
# hidden-terminal collisions.
for slot_us in $SLOT_DURATIONS_US; do
    python3 emane/bridge.py --file "$COORDS" --slot-us "$slot_us" --out "$RUN/optimised_${slot_us}us.xml"
    python3 emane/bridge.py --file "$COORDS" --slot-us "$slot_us" \
        --slots emane/distance1_schedule.json --out "$RUN/distance1_${slot_us}us.xml"
    run_schedule "optimised_${slot_us}us" "$RUN/optimised_${slot_us}us.xml"
    run_schedule "distance1_${slot_us}us" "$RUN/distance1_${slot_us}us.xml"
done
