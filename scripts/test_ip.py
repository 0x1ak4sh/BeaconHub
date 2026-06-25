#!/usr/bin/env python3
import subprocess
import re

def get_interface_ip(interface):
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", interface],
            capture_output=True, text=True, timeout=5
        )
        print(f"Output for {interface}:")
        print(result.stdout)
        print(f"Return code: {result.returncode}")
        match = re.search(r"inet\s+([\d.]+)/", result.stdout)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error: {e}")
    return None

for iface in ["client0", "client1", "client2"]:
    ip = get_interface_ip(iface)
    print(f"{iface} -> {ip}")
    print("-" * 40)
