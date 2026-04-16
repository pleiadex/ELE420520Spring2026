#!/usr/bin/env bash
# Exit 0 if Project 4 Zeek + Mininet checks pass; non-zero otherwise.
set -euo pipefail
cd "$(dirname "$0")"
PCAP="${1:-data_aggregator.pcap}"
HLTO="./dnp3m_analyzer/dnp3m-analyzer.hlto"
ZEEK="./detect_mitm.zeek"

fail() { echo "VERIFY FAIL: $*" >&2; exit 1; }

echo "== 1) Offline pcap (expect no ALERT, no ERROR) =="
rm -f dnp3m.log
zeek -Cr "$PCAP" "$HLTO" "$ZEEK"
if grep -q ALERT dnp3m.log 2>/dev/null; then
  fail "clean pcap produced ALERT"
fi
if grep -q "ERROR on parsing" dnp3m.log 2>/dev/null; then
  fail "clean pcap produced ERROR on parsing"
fi
cp -f dnp3m.log no_mitm.log
echo "OK: offline pcap (also saved no_mitm.log)"

echo "== 2) Mininet + Zeek live batch (expect ALERT, index 23 relay 1.63 vs DA 1.79) =="
sudo python3 run_mininet_cli.py
if ! test -f mitm_live.log; then
  fail "mitm_live.log missing"
fi
if ! grep -q "ALERT:" mitm_live.log; then
  fail "Mininet run did not produce ALERT in mitm_live.log"
fi
# Relay-side table should contain 1.63 for index 23; DA/CC side 1.79 (FDIA)
grep -q '\[23\] = 1.63,' mitm_live.log || fail "expected [23] = 1.63 (from relays)"
grep -q '\[23\] = 1.79,' mitm_live.log || fail "expected [23] = 1.79 (to control center)"
cp -f mitm_live.log mitm.log
echo "OK: Mininet MITM detection (mitm.log updated from mitm_live.log)"
echo "VERIFY: all checks passed"
