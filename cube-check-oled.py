
import time
import subprocess
import os
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
import threading

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
oled_lines = [""] * 5
dot_count = 0
oled_state = {
    "current": "Idle",
}

def update_dots():
    global dot_count
    dot_count = (dot_count + 1) % 4
    return "." * dot_count

def oled_print(text):
    global oled_lines
    oled_lines.pop()
    oled_lines.insert(0, str(text))

    # draw to OLED
    with canvas(device) as draw:
        draw.text((0, 0), "Terralog V5.2", fill="white")
        draw.line((0, 14, 127, 14), fill="white")
        for i, line in enumerate(oled_lines):
            draw.text((0, 16 + i * 10), line[:20], fill="white")

def oled_render():
    dots = update_dots()

    with canvas(device) as draw:
        # Title
        draw.text((0, 0), "Terralog V5.2", fill="white")
        draw.line((0, 12, 127, 12), fill="white")

        # Sections
        draw.text((0, 16), "Cube Detected!", fill="white")
        draw.text((0, 28), f"Stabilizing Cube{dots}", fill="white")
        draw.text((0, 40), f"30s timer: {oled_state['current']}", fill="white")
def oled_render_nocube():
    with canvas(device) as draw:
        # Title
        draw.text((0, 0), "Terralog V5.2", fill="white")
        draw.line((0, 12, 127, 12), fill="white")

        # Sections
        draw.text((0, 16), "No cube detected!", fill="white")
        draw.text((0, 28), f"Please insert Cube...", fill="white")

def set_current(text):
    oled_state["current"] = str(text)

def oled_loop():
    global oled_running
    while oled_running:
        oled_render()
        time.sleep(0.1)

def oled_clear():
    global oled_lines

    # reset buffer
    oled_lines = [""] * len(oled_lines)

    # clear display
    with canvas(device) as draw:
        pass  # draws nothing → blank screen

def cube_connect():
    #result = subprocess.run(["lsusb"], capture_output=True, text=True)
    return os.path.exists("/dev/ttyACM0")

count = str(3)
was_connected = False

while True:
    connected = cube_connect()
    if connected and not was_connected:
        print("Cube Connected")
        oled_running = True
        threading.Thread(target=oled_loop, daemon=True).start()
        timer = 0
        while timer<30:
            set_current(timer)
            timer+=1
            time.sleep(1)
        oled_running = False
        subprocess.run(["/home/pi/Documents/enviro/bin/python", "-u", "/home/pi/Documents/terralog-raspi/download-oled.py"])
    elif not connected and was_connected:
        print("Cube Disconnected")
        timer = 0
    elif not connected:
        print("No Cube yet")
        oled_render_nocube()
    was_connected = connected
    time.sleep(2)
