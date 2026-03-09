#!/bin/env python3
import sys
from pathlib import Path
import time
import shutil
import os

def test(input_folder,time_prev=0):
    start = time.perf_counter()
    time_prev = int(float(time_prev))
    schema = {

        "GPS": [
            ("TimeUS", "q"),
            ("Status", "f"),
            ("GMS", "q"),
            ("GWk", "i"),
            ("Spd", "f"),
        ],

        "POS": [
            ("TimeUS", "q"),
            ("Lat", "f"),
            ("Lng", "f"),
            ("RelHomeAlt", "f"),
        ],

        "RCOU": [
            ("TimeUS", "q"),
            ("C11", "f"),
        ],

        "BAT1": [
            ("TimeUS", "q"),
            ("Curr", "f"),
        ],

        "BAT2": [
            ("TimeUS", "q"),
            ("Curr", "f"),
        ],

        "MSG": [
            ("TimeUS", "q"),
            ("Mission", "i"),
            ("Action", "12s"),
        ],

        "CMD": [
            ("TimeUS", "q"),
            ("Prm3", "i"),
        ],
        
        "MODE": [
            ("TimeUS", "q"),
            ("Mode", "f"),
            ("ModeNum", "f"),
            ("Rsn", "f"),
        ],
        
        "CTUN": [
            ("TimeUS", "q"),
            ("ThO", "f"),
        ]
    }
    print("Running main process...")
    input_folder = Path(__file__).resolve().parent/input_folder
    destination = Path(__file__).resolve().parent.parent/"TERALOG"
    tz = 8

    from newextract import extract
    results = extract(input_folder, tz, 1)


    for item in results:
        df = item["data"]
        if df.empty:
            continue

        base = Path(item["file"]).stem
        sysid = item["sysid"] or "Unknown"
        date = str(item["gps_time"]) or "Unknown"
        date_file = str(item["file_time"]) or "Unknown"
        
        out_name = f"D16-{sysid}_{base}_{date_file}.csv"
        out_path = input_folder/ "output" / "csv" / date / f"D16-{sysid}"
        out_path.mkdir(parents=True, exist_ok=True)
        output = out_path/out_name

        df.to_csv(output, index=False)
        shutil.copy(output,destination)
        print(f"Csv saved into {output} and {destination}")

        from compressor import new_process_csv_folder
        print(f"Making BIN files from {output}")
        out_bin = input_folder/ "output" / "bin" / date / f"D16-{sysid}"
        out_bin.mkdir(parents=True, exist_ok=True)
        bin_name = f"D16-{sysid}_{base}_{date_file}.bin"
        bin_output = out_bin/bin_name
        new_process_csv_folder(out_path,out_bin,schema)
        print(f"Bin file saved into {bin_output}")
    total_elapsed = time.perf_counter() - start + time_prev + 30 #30 being the delay from USB detection to connecting
    print("-----------------------------------------------")
    print(f"Program runtime = {total_elapsed} Seconds")

'''
def _process_upload(output_folder):
    from newupload import run_upload
    print("Running upload process...")
    try:
        run_upload(output_folder,"1uEJtnmgQBIxx8MbXkSFEUuAuHwTEsOV9")
        #Default: 1LhMM5Co1vtm0BExLjakGUEkh72-jDguI
    except Exception as e:
        print(f"Error: {e}")
'''

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: logger-cli.py <input_folder>")
        sys.exit(1)
    elif len(sys.argv) < 3:
        test(sys.argv[1])
    else:
        test(sys.argv[1],sys.argv[2])
