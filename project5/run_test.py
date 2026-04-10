#!/usr/bin/env python3
"""
Automated Mininet test: start relays, data aggregator, run control_center (auto demo).
Requires: mininet. Run: sudo python3 run_test.py
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch
    from mininet.log import setLogLevel

    setLogLevel("warning")

    net = Mininet(controller=Controller, switch=OVSSwitch)
    net.addController("c1")

    s1 = net.addSwitch("s1", mac=11)
    s2 = net.addSwitch("s2", mac=12)
    s3 = net.addSwitch("s3", mac=13)
    cc = net.addHost("cc", ip="10.0.0.1")
    da = net.addHost("da", ip="10.0.0.20")
    relay1 = net.addHost("relay1", ip="10.0.0.11")
    relay2 = net.addHost("relay2", ip="10.0.0.12")
    relay3 = net.addHost("relay3", ip="10.0.0.13")
    relay4 = net.addHost("relay4", ip="10.0.0.14")

    net.addLink(s1, s2)
    net.addLink(s2, s3)
    net.addLink(cc, s1)
    net.addLink(da, s2)
    net.addLink(relay1, s3)
    net.addLink(relay2, s3)
    net.addLink(relay3, s3)
    net.addLink(relay4, s3)

    net.start()
    proj_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        for host, script in [
            (relay1, "relay1.py"),
            (relay2, "relay2.py"),
            (relay3, "relay3.py"),
            (relay4, "relay4.py"),
        ]:
            host.popen(
                ["python3", os.path.join(proj_dir, script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.15)

        time.sleep(0.4)
        da.popen(
            ["python3", os.path.join(proj_dir, "data_aggregator.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.5)

        cc_proc = cc.popen(
            [
                "python3",
                os.path.join(proj_dir, "control_center.py"),
                "--rounds",
                "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=proj_dir,
        )
        out, err = cc_proc.communicate(timeout=30)
        print(out.decode())
        if err:
            print(err.decode(), file=sys.stderr)
    finally:
        net.stop()


if __name__ == "__main__":
    main()
