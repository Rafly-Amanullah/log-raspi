from pymavlink import mavutil
from datetime import datetime, timezone
from serial.serialutil import SerialException
import time
import os
from pathlib import Path
import subprocess
import threading

#OLED Stuff
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
oled_lines = [""] * 5
oled_state = {
    "current": "Idle",
    "latest": "-",
    "error": "-"
}
spinner = ["|", "/", "-", "\\"]
spinner_index = 0
oled_running = False
#---------

port = "/dev/ttyACM0"
baud = 115200
log_timeout = 2.0

#OLED Functions
def update_spinner():
    global spinner_index
    spinner_index = (spinner_index + 1) % len(spinner)
    return spinner[spinner_index]

def oled_render():
    spin = update_spinner()

    with canvas(device) as draw:
        # Title
        draw.text((0, 0), "Terralog V5.2", fill="white")
        draw.line((0, 12, 127, 12), fill="white")

        # Sections
        draw.text((0, 16), f"DLO: {oled_state['current']} {spin}", fill="white")
        draw.text((0, 28), f"DON: {oled_state['latest']}", fill="white")
        draw.text((0, 40), f"ERR: {oled_state['error']}", fill="white")

def set_current(text):
    oled_state["current"] = str(text)
    oled_render()

def set_latest(log_id):
    oled_state["latest"] = str(log_id)
    oled_render()

def set_error(err):
    oled_state["error"] = str(err)
    oled_render()

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

def oled_clear():
    global oled_lines

    # reset buffer
    oled_lines = [""] * len(oled_lines)

    # clear display
    with canvas(device) as draw:
        pass  # draws nothing -> blank screen


def oled_loop():
    global oled_running
    while oled_running:
        oled_render()
        time.sleep(0.1)
#-----------
def connect():
    print("Connecting...")
    oled_print("Connecting")
    mav = mavutil.mavlink_connection(port, baud)
    print("Waiting for heartbeat...")
    oled_print("Waiting for heartbeat...")
    mav.wait_heartbeat

    print("Heartbeat received")
    oled_print("Connected!")
    print(f"System ID: {mav.target_system}")
    print(f"Component ID: {mav.target_component}")
    oled_print(f"System ID: {mav.target_system}")
    oled_print(f"Component ID: {mav.target_component}")
    oled_clear()
    return mav

def get_latest_log_info(mav):
    mav.mav.log_request_list_send(
        mav.target_system,
        mav.target_component,
        0,
        0xFFFF
    )
    log_dates={}
    expected=None
    retry_interval = 3
    last_request = 0

    while True:
        if time.time() - last_request > retry_interval:
            print("Requesting log list")
            
            mav.mav.log_request_list_send(
                mav.target_system,
                mav.target_component,
                0,
                0xFFFF
            )
            last_request = time.time()
        msg = mav.recv_match(type="LOG_ENTRY", timeout=1)
        if not msg:
            continue
        if expected is None:
            expected=msg.num_logs
            print(f"Expecting {expected} number of logs")
        
        utc_time = datetime.fromtimestamp(msg.time_utc, timezone.utc)
        local_time = utc_time.astimezone()

        log_dates[msg.id] = local_time

        if expected and len(log_dates) >= expected:
            newest_log = max(log_dates, key=log_dates.get)
            print(f"Newest log: {newest_log} at {log_dates[newest_log]}")
            return newest_log

def get_logs_amounts(mav):
    mav.mav.log_request_list_send(
        mav.target_system,
        mav.target_component,
        0,
        0xFFFF
    )
    log_date = {}
    expected = None
    retry_interval = 3
    last_request = 0

    while True:
        if time.time()-last_request>retry_interval:
            oled_clear()
            print("Request log list")
            oled_print("please wait...")
            oled_print("Requesting log,")
            mav.mav.log_request_list_send(
                mav.target_system,
                mav.target_component,
                0,
                0xFFFF
            )
            last_request = time.time()
        
        msg = mav.recv_match(type = "LOG_ENTRY", timeout = 1)
        if not msg:
            continue
        if expected is None:
            expected = msg.num_logs
            print (f"Expecting {expected} amount of logs")
        utc_time = datetime.fromtimestamp(msg.time_utc, timezone.utc)
        local_time = utc_time.astimezone()
        log_date[msg.id] = local_time

        if expected and len(log_date) >= expected:
            break
    sorted_logs = sorted(log_date.items(), key = lambda x:x[1], reverse=True)
    oled_clear()
    return sorted_logs


def download_log(mav, log_num):
    path = Path(__file__).resolve().parent/"bin"
    path.mkdir(exist_ok=True)
    filename = f"{log_num:08d}.BIN"
    file_path = path / filename
    #print(f"Downloading log {log_num} as {filename}")
    retries = 3
    global oled_running
    oled_running = True
    threading.Thread(target=oled_loop, daemon=True).start()
    for attempts in range(1, retries+1):
        print(f"Download attempt {attempts}")
        set_current(f"{log_num}-Attempt{attempts}")
        f = open(file_path,"wb")
        mav.mav.log_request_data_send(
            mav.target_system,
            mav.target_component,
            log_num,
            0,
            0xFFFFFFFF
        )

        download_ofs = 0
        last_packet_time = time.time()
        start_time = time.perf_counter()
        success = False

        while True:
            msg = mav.recv_match(blocking=True, timeout=1)
            if time.perf_counter() - start_time > 90:
                print("Download too slow!")
                break

            if msg is None:
                if time.time() - last_packet_time > 90:
                    print("Timeout waiting for data")
                    break
                continue
            if msg.get_type() != "LOG_DATA":
                continue

            last_packet_time = time.time()

            if msg.ofs != download_ofs:
                f.seek(msg.ofs)
                print("msg.ofs != download_ofs")
                download_ofs=msg.ofs
            
            if msg.count > 0:
                s = bytearray(msg.data[:msg.count])
                f.write(s)
                download_ofs += msg.count
            
            if msg.count==0 or msg.count < 90:
                print("Download finished")
                success = True
                break

        f.close()
        if success:
            elapsed = time.perf_counter() - start_time
            size = os.path.getsize(file_path)
            print (f"Saved {size} bytes in {elapsed:.1f}s ({size/(1000*elapsed):.1f} kB/s) at {file_path}")
            set_latest(f"{log_num}@{size/(1000*elapsed):.1f} kB/s")
            oled_running = False
            return
        print("Restarting download...")
        if attempts == 3:
            set_error(log_num)
            oled_running = False

retry_delay = 2

def download_batch(mav,count):
    sorted_logs = get_logs_amounts(mav)
    count = int(count)
    if not sorted_logs:
        print("No logs available")
        return
    amount_todownload = sorted_logs[:count]
    print(f"Requesting {len(amount_todownload)} amount of latest logs")
    for log_id, log_time, in amount_todownload:
        print(f"Downloading Log {log_id}: {log_time}")
        download_log(mav,log_id)

def get_latest_week(mav):
    sorted_logs = get_logs_amounts(mav)
    if not sorted_logs:
        print("No logs found")
        return
    current_date = sorted_logs[0][1].date()
    print (f"Downloading a week worth of logs starting from {current_date}")
    count = 0
    week = 1
    for log_id, log_time in sorted_logs:
        if log_time.date() != current_date:
            print("Changing date...")
            current_date = log_time.date()
            print(f"Date changed into {current_date}")
            week += 1
            if week > 1:
                week = week-1
                break
        if log_time.date() == current_date:
            print(f"Downloading log {log_id}: ({log_time})")
            download_log(mav,log_id)
            count+=1
        else:
            break
    print (f"Finisihed downloading {count} amount of logs from {week} weeks")

def main():
    while True:
        mav = None
        total_start = time.perf_counter()

        try:
            mav = connect()
            #log_id = get_latest_log_info(mav)
            #get_latest_week(mav)
            download_batch(mav,1)
            #download_log(mav, 221)

            total_elapsed = time.perf_counter() - total_start
            str_elapsed = str(total_elapsed)
            print(f"Total download runtime: {total_elapsed:.2f} seconds")

            break  # success → exit loop

        except SerialException:
            print("Cube disconnected during transfer — retrying...")

        except Exception as e:
            print(f"Unexpected error: {e} — retrying...")

        finally:
            if mav:
                try:
                    mav.close()
                    print("Mav closed!")
                except Exception:
                    pass
        time.sleep(retry_delay)
    subprocess.run(["/home/pi/Documents/enviro/bin/python","-u","/home/pi/Documents/terralog-raspi/logger-cli-oled.py","bin",str_elapsed])

if __name__ == "__main__":
    main()
