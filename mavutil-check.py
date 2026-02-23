print("mavutil-check")
from pymavlink import mavutil
import time
from datetime import datetime,timezone

print("Connecting")
mav = mavutil.mavlink_connection("/dev/ttyACM0", baud=115200)

print("Waiting for heartbeat")
mav.wait_heartbeat()

print("Heartbeat received!")
print("System ID:", mav.target_system)
print("Component ID:", mav.target_component)
mav.mav.log_request_list_send(mav.target_system,mav.target_component,0,0xFFFF)
logs={}
log_date={}
last=time.time()
first_log=None
expected = None
unix_time = None
utc_time = None
local_time = None
tz = 8
chunk_size=1024
window_size = 30
offset = 0
start=time.perf_counter()
loop = True
while loop:
    msg = mav.recv_match(type='LOG_ENTRY', timeout=1)

    if msg:
        last = time.time()

        if expected is None:
            expected = msg.num_logs
            last_log = msg.last_log_num
            first_log = last_log - expected + 1
            #print(f"Log Range: {first_log} - {last_log}")

        unix_time = msg.time_utc
        utc_time = datetime.fromtimestamp(unix_time,tz=timezone.utc)
        local_time = utc_time.astimezone()

        log_date[msg.id] = local_time
        logs[msg.id] = msg.size


        #print(f"Log {msg.id} ({len(logs)}/{expected})")

        if len(logs) >= expected:
            newest_log = max(log_date, key=log_date.get)
            new_log_size = logs[newest_log]
            print("Highest value key:", newest_log)
            print(f"Newest:Log {newest_log} at {log_date[newest_log]}")
            print("All logs received, Downloading Log",newest_log)
            download_start=time.perf_counter()
            log_num = newest_log                 # change this
            out = f"{log_num:08d}.BIN"
            f = open(out, "wb")
            mav.mav.log_request_data_send(
                mav.target_system,
                mav.target_component,
                log_num,
                0,
                0xFFFFFFFF
            )
            download_ofs = 0
            start_time = time.time()
            last_packet_time = time.time()

            while True:
                msg = mav.recv_match(blocking=True, timeout=1)

                if msg is None:
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
            time_elapsed=time.perf_counter()-download_start
            total_time_elapsed=time.perf_counter()-start
            print(f"Download time elapsed:{time_elapsed} seconds")
            print(f"Total time elapsed:{total_time_elapsed} seconds")
            mav.close()
            loop = False

'''
while True:
    msg=mav.recv_match(type='LOG_ENTRY',timeout=2)
    if msg == None:
        continue
    if first_log is None:
        first_log = msg.last_log_num - msg.num_logs+1
        last_log = msg.last_log_num
        expected = msg.num_logs
        print(f"Log Range: {first_log} - {last_log}")
    if msg.id == first_log:
        print("Synced at first log!")
        logs[msg.id]=msg.size
        last=time.time()
        break
    if msg.id is not first_log and time.time()-last>3:
        print("Retrying...")
        mav.mav.log_request_list_send(mav.target_system,mav.target_component,0,0xFFFF)
    else:
        print(f"First_log not found, currently:{msg.id}")
        last=time.time()
while True:
    msg=mav.recv_match(type='LOG_ENTRY',timeout=2)
    if msg:
        print(f"logs ID = {msg.id}, Size={msg.size}")
        last=time.time()
    if expected and time.time()-last>2:
        break
print("Done!")
mav.close()
'''