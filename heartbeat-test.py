import os
os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP
import time

master = mavutil.mavlink_connection(
    '/dev/ttyACM0',
    baud=115200,
    mavlink_version=2
)

master.wait_heartbeat()
print("MAVLink2:", master.mavlink20())

# Send GCS heartbeat (important)
master.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0, 0, 0
)

ftp = MAVFTP(master, 1, 1)

print("Listing logs directory...")

# This returns a MAVFTPReturn object
ret = ftp.cmd_list(["/"])
print("Return code:", ret.return_code)

if ret.return_code == 0:
    print("Success")
else:
    print("Error:", ret.error_code)

ret.display_message()
#print(dir(ret))
# Now let MAVFTP internally manage communication
'''
start = time.time()

while not ret.done:
    master.recv_match(blocking=True, timeout=0.5)
    ftp.idle_task()

    if time.time() - start > 15:
        print("Timeout")
        break

if ret.success:
    print("Files:")
    for f in ret.data:
        print(f)
else:
    print("FTP failed:", ret.error)
'''