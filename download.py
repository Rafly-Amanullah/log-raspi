from pymavlink import mavutil
from datetime import datetime, timezone
from serial.serialutil import SerialException
import time
import os

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

        
def download_log(mav, log_num):
    filename = f"{log_num:08d}.BIN"
    print(f"Downloading log {log_num} as {filename}")

    f = open(filename,"wb")

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
    size = os.path.getsize(filename)
    print (f"Saved {size} bytes in {elapsed:.1f}s ({size/(1000*elapsed):.1f} kB/s)")

retry_delay = 2

def main():
    while True:
        mav = None
        total_start = time.perf_counter()

        try:
            mav = connect()
            log_id = get_latest_log_info(mav)
            download_log(mav, log_id)

            total_elapsed = time.perf_counter() - total_start
            print(f"Total program runtime: {total_elapsed:.2f} seconds")

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

if __name__ == "__main__":
    main()
