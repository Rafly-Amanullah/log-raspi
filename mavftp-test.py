from pymavlink import mavutil, mavftp
print ("Connecting...")
master = mavutil.mavlink_connection("/dev/ttyACM0")
hb = master.wait_heartbeat()
print("Heartbeat OK — connected")
print("Heartbeat from system", hb.get_srcSystem(),
      "component", hb.get_srcComponent())

target_system = hb.get_srcSystem()
target_component = hb.get_srcComponent()
ftp = mavftp.MAVFTP( master, target_system, target_component)
#print(dir(ftp))

print("Listing logs...")
files = ftp.cmd_list(["/"])
print("Last op:", ftp.last_op)
while not ftp.done:
    msg = master.recv_match(blocking=True, timeout=1)
    if msg:
        print(msg)
        ftp.process_ftp_reply(msg)
print("Directory contents:")
for filename in ftp.list_result:
    print("✦", filename)


'''
print("Listing logs")
files = ftp.listdir("/APM/LOGS")
print (files)

log_files = sorted([f for f in files if files.endswith(".BIN")])
latest = log_files[-1]

print(f"Downloading: {latest}")
ftp.get("APM/LOGS"+latest, latest)
print("Done!")
'''