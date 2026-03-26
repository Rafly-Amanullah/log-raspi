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

        
def old_download_log(mav, log_num):
    path = Path(__file__).resolve().parent/"bin"
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
            break

    f.close()
    elapsed = time.perf_counter() - start_time
    size = os.path.getsize(file_path)
    print (f"Saved {size} bytes in {elapsed:.1f}s ({size/(1000*elapsed):.1f} kB/s) at {file_path}")

def download_log(mav, log_num):
    path = Path(__file__).resolve().parent/"bin"
    path.mkdir(exist_ok=True)
    filename = f"{log_num:08d}.BIN"
    file_path = path / filename
    #print(f"Downloading log {log_num} as {filename}")
    retries = 3
    for attempts in range(1, retries+1):
        print(f"Download attempt {attempts}")
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
            return
        print("Restarting download...")

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

def get_latest_day(mav):
    sorted_logs = get_logs_amounts(mav)
    if not sorted_logs:
        print("No logs found")
        return
    newest_date = sorted_logs[0][1].date()
    print(f"Downloading all logs from date: {newest_date}")
    count = 0
    for log_id, log_time in sorted_logs:
        if log_time.date() == newest_date:
            print(f"Downloading log {log_id}: ({log_time})")
            download_log(mav,log_id)
            count += 1
        else:
            break
    print(f"Finished downloading {count} logs from {newest_date}")

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
            if week > 7:
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
            download_log(mav, 221)

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
    #subprocess.run(["/home/pi/Documents/enviro/bin/python","-u","/home/pi/Documents/terralog-raspi/logger-cli.py","bin",str_elapsed])

if __name__ == "__main__":
    main()
