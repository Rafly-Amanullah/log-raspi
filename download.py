from pymavlink import mavutil
from datetime import datetime, timezone
from serial.serialutil import SerialException
import time
import os
from pathlib import Path
import subprocess
import sys

port = "/dev/ttyACM0"
baud = 115200
log_timeout = 2.0

def connect():
    print("Connecting...")
    mav = mavutil.mavlink_connection(port, baud)
    print("Waiting for heartbeat...")
    mav.wait_heartbeat

    print("Heartbeat received")
    print(f"System ID: {mav.target_system}")
    print(f"Component ID: {mav.target_component}")
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
            print("Request log list")
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
    return sorted_logs

        
def download_log(mav, log_num):
    path = Path.cwd()/"bin"
    path.mkdir(exist_ok=True)
    filename = f"{log_num:08d}.BIN"
    file_path = path / filename
    #print(f"Downloading log {log_num} as {filename}")

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

    while True:
        msg = mav.recv_match(blocking=True, timeout=1)

        if msg is None:
            if time.time() - last_packet_time > log_timeout:
                print("Timeout waiting for data")
                break
            continue
        if msg.get_type() != "LOG_DATA":
            continue

        last_packet_time = time.time()

        if msg.ofs != download_ofs:
            f.seek(msg.ofs)
            download_ofs=msg.ofs
        
        if msg.count > 0:
            s = bytearray(msg.data[:msg.count])
            f.write(s)
            download_ofs += msg.count
        
        if msg.count==0 or msg.count < 90:
            print("Download finished")
            break
    f.close()
    elapsed = time.perf_counter() - start_time
    size = os.path.getsize(file_path)
    print (f"Saved {size} bytes in {elapsed:.1f}s ({size/(1000*elapsed):.1f} kB/s) at {file_path}")

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
        #time.sleep(retry_delay)


def main(count):
    while True:
        mav = None
        total_start = time.perf_counter()

        try:
            mav = connect()
            #log_id = get_latest_log_info(mav)
            download_batch(mav, count)

            total_elapsed = time.perf_counter() - total_start
            str_elapsed = str(total_elapsed)
            #print(f"Total program runtime: {total_elapsed:.2f} seconds")

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
    subprocess.run(["/home/pi/Documents/enviro/bin/python","/home/pi/Documents/terralog-raspi/logger-cli.py","bin",str_elapsed])

if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Usage: download.py <amount of files>")
        sys.exit()
    main(sys.argv[1])
