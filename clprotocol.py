import os
import time
from pymavlink import mavutil

LOG_NUMBER = 130                 # change this
OUTPUT_FILE = "log1.bin"
PORT = "/dev/ttyACM0"
BAUD = 115200

# connect
master = mavutil.mavlink_connection(PORT, baud=BAUD)
master.wait_heartbeat()
print("Connected")

target_system = master.target_system
target_component = master.target_component

# open file
f = open(OUTPUT_FILE, "wb")

# request entire log
master.mav.log_request_data_send(
    target_system,
    target_component,
    LOG_NUMBER,
    0,
    0xFFFFFFFF
)

print("Downloading log", LOG_NUMBER)

download_ofs = 0
start_time = time.time()
last_packet_time = time.time()

while True:
    msg = master.recv_match(blocking=True, timeout=1)

    if msg is None:
        # timeout check
        if time.time() - last_packet_time > 2:
            print("No data received, ending")
            break
        continue

    if msg.get_type() == "LOG_DATA":

        last_packet_time = time.time()

        # seek if needed
        if msg.ofs != download_ofs:
            f.seek(msg.ofs)
            download_ofs = msg.ofs

        # write data
        if msg.count > 0:
            s = bytearray(msg.data[:msg.count])
            f.write(s)
            download_ofs += msg.count

        # finished condition
        if msg.count == 0 or msg.count < 90:
            print("Download finished")
            break

f.close()

dt = time.time() - start_time
size = os.path.getsize(OUTPUT_FILE)
print(f"Saved {size} bytes in {dt:.1f}s ({size/(1000*dt):.1f} kB/s)")

# tell autopilot we're done
master.mav.log_request_end_send(
    target_system,
    target_component
)
