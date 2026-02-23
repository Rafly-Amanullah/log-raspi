#!/usr/bin/env python3
import sys
import subprocess
import time

action = sys.argv[1]
dev = sys.argv[2]

def usb_name_search():
    result = subprocess.run(["udevadm", "info", "-n", dev], capture_output = True, text = True)
    return "orange" in result.stdout.lower()
if action == "add":
    time.sleep(1)
    if usb_name_search():
        subprocess.run(["systemctl","start","mavproxy-orange.service"])
elif action == "remove":
    subprocess.run(["systemctl", "stop", "mavproxy-orange.service"])