
import time
import subprocess
import os
def cube_connect():
    #result = subprocess.run(["lsusb"], capture_output=True, text=True)
    return os.path.exists("/dev/ttyACM0")

count = 3
was_connected = False

while True:
    connected = cube_connect()
    if connected and not was_connected:
        print("Cube Connected")
        subprocess.run(["/home/pi/Documents/enviro/bin/python","/home/pi/Documents/terralog-raspi/download.py",count])
    elif not connected and was_connected:
        print("Cube Disconnected")
    elif not connected:
        print("No Cube yet")
    was_connected = connected
    time.sleep(2)
