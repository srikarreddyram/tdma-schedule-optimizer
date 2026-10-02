"""Traffic probe run inside one radio's network namespace.

Broadcasts numbered UDP packets over the radio interface while counting the
packets heard from every other radio, then writes the tallies as JSON.

Usage: python3 emane/traffic.py --nem 3 --count 300 --out out/node3.json
"""
import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

PORT = 5001
BROADCAST = "10.100.0.255"
DEVICE = b"emane0"
PAYLOAD_BYTES = 64


def listen(sock, heard, stop):
    while not stop.is_set():
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            continue
        sender = int(data.split()[0])
        heard[sender] = heard.get(sender, 0) + 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--nem", type=int, required=True)
    parser.add_argument("--count", type=int, default=300, help="packets to send")
    parser.add_argument("--interval", type=float, default=0.02, help="seconds between packets")
    parser.add_argument("--start", type=float, default=0.0, help="epoch time to begin sending")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver.bind(("", PORT))
    receiver.settimeout(0.2)
    heard, stop = {}, threading.Event()
    listener = threading.Thread(target=listen, args=(receiver, heard, stop))
    listener.start()

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sender.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, DEVICE)

    # Every radio starts at the same instant so their transmissions overlap in time.
    time.sleep(max(0.0, args.start - time.time()))
    for sequence in range(args.count):
        message = f"{args.nem} {sequence} ".encode().ljust(PAYLOAD_BYTES, b".")
        sender.sendto(message, (BROADCAST, PORT))
        time.sleep(args.interval)

    time.sleep(2.0)  # let queued packets drain before counting stops
    stop.set()
    listener.join()
    args.out.write_text(json.dumps({"nem": args.nem, "sent": args.count, "heard": heard}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
