#!/usr/bin/env python3
"""
Automated test script that runs the full Project 2 flow using Mininet.
Runs relays, data aggregator, and control center in host namespaces.
Optionally captures network traffic with tshark for Wireshark export.
"""

import sys
import os
import time
import subprocess
import argparse
import shutil

# Add project2 to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main(capture=False):
    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch
    from mininet.log import setLogLevel
    from mininet.util import quietRun

    setLogLevel('warning')  # Reduce Mininet output

    print("Building Mininet network...")
    net = Mininet(controller=Controller, switch=OVSSwitch)
    net.addController('c1')

    # Topology from build_net.py
    s1 = net.addSwitch("s1", mac=11)
    s2 = net.addSwitch("s2", mac=12)
    s3 = net.addSwitch("s3", mac=13)
    cc = net.addHost('cc', ip='10.0.0.1')
    da = net.addHost('da', ip='10.0.0.20')
    relay1 = net.addHost('relay1', ip='10.0.0.11')
    relay2 = net.addHost('relay2', ip='10.0.0.12')
    relay3 = net.addHost('relay3', ip='10.0.0.13')
    relay4 = net.addHost('relay4', ip='10.0.0.14')

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
    output_path = os.path.join(proj_dir, 'network_trace.pcapng')
    tmp_capture = '/tmp/project2_network_trace.pcapng'
    tshark_proc = None

    try:
        if capture:
            # Start tshark on Data Aggregator host to capture traffic (as per Project 2 spec)
            print("Starting tshark capture on Data Aggregator (da-eth0)...")
            tshark_proc = da.popen(
                ['tshark', '-i', 'da-eth0', '-w', tmp_capture, '-a', 'duration:8'],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            time.sleep(0.5)

        # Start relays (servers)
        print("Starting Relay 1...")
        r1 = relay1.popen(['python3', os.path.join(proj_dir, 'relay1.py')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.2)
        print("Starting Relay 2...")
        r2 = relay2.popen(['python3', os.path.join(proj_dir, 'relay2.py')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.2)
        print("Starting Relay 3...")
        r3 = relay3.popen(['python3', os.path.join(proj_dir, 'relay3.py')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.2)
        print("Starting Relay 4...")
        r4 = relay4.popen(['python3', os.path.join(proj_dir, 'relay4.py')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)

        # Start data aggregator
        print("Starting Data Aggregator...")
        da_proc = da.popen(['python3', os.path.join(proj_dir, 'data_aggregator.py')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)

        # Run control center with auto-enter (pipe newlines for input prompts)
        print("Running Control Center...")
        cc_script = os.path.join(proj_dir, 'control_center.py')
        cc_proc = cc.popen(
            ['sh', '-c', f'echo -e "\\n\\n\\n" | python3 {cc_script}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=proj_dir
        )

        # Wait for control center to finish
        cc_out, cc_err = cc_proc.communicate(timeout=15)
        cc_out = cc_out.decode()
        cc_err = cc_err.decode()

        print("\n" + "="*60)
        print("CONTROL CENTER OUTPUT (measurements):")
        print("="*60)
        print(cc_out)
        if cc_err:
            print("STDERR:", cc_err)

        # Verify we got all 36 measurements
        import util
        expected_indices = [11,12,13,14,21,22,23,24,31,32,33,34,41,42,43,44,51,52,53,54,61,62,63,64,71,72,73,74,81,82,83,84,91,92,93,94]
        expected_values = {11:1.00,12:0.00,13:71.95,14:24.07,21:1.00,22:9.67,23:163.00,24:14.46,31:1.00,32:4.77,33:85.00,34:-3.65,41:0.99,42:-2.41,43:0.00,44:0.00,51:0.98,52:-4.02,53:-90.00,54:-30.00,61:1.01,62:1.93,63:0.00,64:0.00,71:0.99,72:0.62,73:-100.00,74:-35.00,81:1.00,82:3.80,83:0.00,84:0.00,91:0.96,92:-4.35,93:0.00,94:0.00}

        # Parse output for measurement lines (format: "11 :  1.00")
        import re
        parsed = {}
        for m in re.finditer(r'(\d{2})\s*:\s*([-\d.]+)', cc_out):
            idx, val = int(m.group(1)), float(m.group(2))
            if 11 <= idx <= 94 and idx % 10 in (1, 2, 3, 4):  # valid measurement indices
                parsed[idx] = val

        if len(parsed) == 36:
            print("\n*** SUCCESS: All 36 measurements received ***")
            errors = []
            for idx in expected_indices:
                if idx not in parsed:
                    errors.append(f"Missing index {idx}")
                elif abs(parsed[idx] - expected_values[idx]) > 0.01:
                    errors.append(f"Index {idx}: expected {expected_values[idx]}, got {parsed[idx]}")
            if errors:
                print("Validation issues:", errors)
            else:
                print("All values match Table 1.")
        else:
            print(f"\n*** WARNING: Expected 36 measurements, got {len(parsed)} ***")

        if capture and tshark_proc:
            tshark_proc.wait(timeout=12)
            if os.path.exists(tmp_capture):
                shutil.copy(tmp_capture, output_path)
                os.remove(tmp_capture)
                # Fix ownership so user can open in Wireshark without sudo (when run via sudo)
                try:
                    uid = int(os.environ.get('SUDO_UID', os.getuid()))
                    gid = int(os.environ.get('SUDO_GID', os.getgid()))
                    os.chown(output_path, uid, gid)
                except (PermissionError, OSError, ValueError):
                    pass
                size = os.path.getsize(output_path)
                print(f"\n*** Network trace saved: {output_path} ({size} bytes) ***")
            else:
                print("\n*** WARNING: Capture file not found (tshark may need root) ***")

    finally:
        net.stop()
        print("\nMininet stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Project 2 CPS simulation in Mininet')
    parser.add_argument('--capture', '-c', action='store_true', help='Capture network traffic with tshark (saves network_trace.pcapng)')
    args = parser.parse_args()
    main(capture=args.capture)
