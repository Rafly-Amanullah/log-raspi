#!/bin/env python3
import sys
from pathlib import Path
import time

def test(input_folder):
    start = time.perf_counter()
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
    print("Running...")
    input_folder = Path.cwd() / input_folder
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
        
        out_name = f"{base} - SYSID{sysid}.csv"
        out_path = input_folder/ "csv" / date / f"D16-{sysid}"
        out_path.mkdir(parents=True, exist_ok=True)
        output = out_path/out_name

        df.to_csv(output, index=False)
        print(f"Csv saved into {output}")

        from compressor import new_process_csv_folder
        print(f"Making BIN files from {output}")
        out_bin = input_folder/"bin"/date/f"D16-{sysid}"
        out_bin.mkdir(parents=True, exist_ok=True)
        bin_name = f"{base} - SYSID{sysid}.bin"
        bin_output = out_bin/bin_name
        new_process_csv_folder(out_path,out_bin,schema)
        print(f"Bin file saved into {bin_output}")
    total_elapsed = time.perf_counter() - start
    print("-----------------------------------------------")
    print(f"Program runtime = {total_elapsed} Seconds")


def _process_upload(output_folder):
    from uploader import run_upload
    print("Menjalankan proses upload...")
    try:
        run_upload(output_folder,"1uEJtnmgQBIxx8MbXkSFEUuAuHwTEsOV9")
        #Default: 1LhMM5Co1vtm0BExLjakGUEkh72-jDguI
    except Exception as e:
        print(f"[Tidak ada internet] Upload gagal dan dihentikan. Upload ulang melalui tab 'Upload' apabila sudah ada internet. Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test.py <input_folder>")
        sys.exit(1)
    test(sys.argv[1])
