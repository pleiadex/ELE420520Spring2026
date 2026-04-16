#!/usr/bin/env python3
"""
Run Project 4 Mininet topology without X11: uses Mininet Python API (host.cmd).

Usage (must be root for Mininet):
  sudo python3 run_mininet_cli.py              # batch: Zeek + relays + DA + control center, then exit
  sudo python3 run_mininet_cli.py --cli        # start network and drop into Mininet CLI (no xterm)

Batch mode order matches the assignment: Zeek on da-eth0 first, then Python scripts.
"""
import argparse
import os
import sys
import time

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel


def build_topology():
    net = Mininet(controller=Controller, switch=OVSSwitch)
    net.addController("c1", controller=Controller)

    net.addSwitch("s1", mac=11)
    net.addSwitch("s2", mac=12)
    net.addSwitch("s3", mac=13)
    net.addHost("cc", ip="10.0.0.1")
    net.addHost("da", ip="10.0.0.20")
    net.addHost("relay1", ip="10.0.0.11")
    net.addHost("relay2", ip="10.0.0.12")
    net.addHost("relay3", ip="10.0.0.13")
    net.addHost("relay4", ip="10.0.0.14")

    net.addLink("s1", "s2")
    net.addLink("s2", "s3")
    net.addLink("cc", "s1")
    net.addLink("da", "s2")
    net.addLink("relay1", "s3")
    net.addLink("relay2", "s3")
    net.addLink("relay3", "s3")
    net.addLink("relay4", "s3")

    return net


def main():
    parser = argparse.ArgumentParser(description="Project 4 Mininet without xterm")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="After starting the network, open the interactive Mininet CLI (like mn). No batch run.",
    )
    parser.add_argument(
        "--skip-zeek",
        action="store_true",
        help="Batch mode only: do not start Zeek (for quick connectivity test).",
    )
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("Run as root: sudo python3 run_mininet_cli.py ...", file=sys.stderr)
        sys.exit(1)

    setLogLevel("info")

    project4 = os.path.dirname(os.path.abspath(__file__))

    net = build_topology()
    net.build()
    net.start()

    try:
        if args.cli:
            print("Mininet CLI - type 'help' for commands, 'exit' to quit.")
            CLI(net)
        else:
            da = net.get("da")
            cc = net.get("cc")
            # Shell-quote paths for remote sh -c
            p = project4.replace("'", "'\"'\"'")

            if not args.skip_zeek:
                # Zeek must start before other scripts (assignment)
                da.cmd(
                    "sh -c 'cd \"%s\" && rm -f dnp3m.log && "
                    "zeek -C -i da-eth0 ./dnp3m_analyzer/dnp3m-analyzer.hlto ./detect_mitm.zeek "
                    ">zeek_batch.out 2>&1 &'"
                    % p
                )
                time.sleep(2.0)

            for name, script in (
                ("relay1", "relay1.py"),
                ("relay2", "relay2.py"),
                ("relay3", "relay3.py"),
                ("relay4", "relay4.py"),
            ):
                net.get(name).cmd(
                    'sh -c \'cd "%s" && python3 %s >%s.out 2>&1 &\'' % (p, script, name)
                )
            time.sleep(1.0)

            da.cmd(
                'sh -c \'cd "%s" && python3 data_aggregator.py >da_batch.out 2>&1 &\'' % p
            )
            time.sleep(1.5)

            # control_center.py uses three input() prompts; feed newlines
            out = cc.cmd(
                'sh -c \'cd "%s" && printf "\\n\\n\\n" | python3 -u control_center.py\''
                % p
            )
            print("--- control_center.py output ---")
            print(out)

            if not args.skip_zeek:
                da.cmd("sh -c 'pkill -f \"[z]eek.*detect_mitm\" || true'")
                time.sleep(0.5)
                log_path = os.path.join(project4, "dnp3m.log")
                if os.path.isfile(log_path):
                    with open(log_path) as f:
                        log_body = f.read()
                    print("--- tail dnp3m.log ---")
                    print(log_body[-4000:] if len(log_body) > 4000 else log_body)
                mitm_path = os.path.join(project4, "mitm_live.log")
                if os.path.isfile(log_path):
                    import shutil

                    shutil.copy2(log_path, mitm_path)
                    print("Copied Zeek output to", mitm_path)
    finally:
        net.stop()


if __name__ == "__main__":
    main()
