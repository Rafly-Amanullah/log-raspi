import os
import pandas as pd
from pymavlink import mavutil
import re
from datetime import datetime, timedelta, timezone

def extract_gps_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    gps_data = []
    try:
        while (msg := mav.recv_match(type='GPS', blocking=False)):
            gps_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(gps_data)

def extract_pos_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    pos_data = []
    try:
        while (msg := mav.recv_match(type='POS', blocking=False)):
            pos_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(pos_data)

def extract_rcou_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    rcou_data = []
    try:
        while (msg := mav.recv_match(type='RCOU', blocking=False)):
            rcou_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(rcou_data)

def extract_bat_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    bat_data = []
    try:
        while (msg := mav.recv_match(type='BAT', blocking=False)):
            bat_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(bat_data)

def extract_cmd_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    cmd_data = []
    try:
        while (msg := mav.recv_match(type='CMD', blocking=False)):
            d = msg.to_dict()
            if d.get("Prm3") == 1:  # Only keep Prm3 == 1
                cmd_data.append(d)
    finally:
        mav.close()
    return pd.DataFrame(cmd_data)

def extract_mode_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    mode_data = []
    try:
        while (msg := mav.recv_match(type='MODE', blocking=False)):
            mode_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(mode_data)

def extract_sysid_thismav(bin_path: str):
    mav = mavutil.mavlink_connection(bin_path)
    sysid_thismav = None
    try:
        while (msg := mav.recv_match(type='PARM', blocking=False)):
            d = msg.to_dict()
            if d.get("Name") == "SYSID_THISMAV":
                sysid_thismav = int(d.get("Value"))
                break
    finally:
        mav.close()
    return sysid_thismav


def extract_msg_from_bin(bin_path: str) -> pd.DataFrame:
    """
    Extract only MSG entries with 'Mission: <num> RepeatServo'
    """
    mav = mavutil.mavlink_connection(bin_path)
    msg_data = []
    try:
        while (msg := mav.recv_match(type='MSG', blocking=False)):
            d = msg.to_dict()
            text = d.get("Message", "")
            
            # Match only lines like: "Mission: 2 RepeatServo"
            match = re.search(r"Mission:\s*(\d+)\s+RepeatServo", text)
            if match:
                msg_data.append({
                    "mavpackettype": "MSG",
                    "TimeUS": d.get("TimeUS"),
                    "Mission": int(match.group(1)),
                    "Action": "RepeatServo"
                })
    finally:
        mav.close()
    return pd.DataFrame(msg_data)

def extract_ctun_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    ctun_data = []
    try:
        while (msg := mav.recv_match(type='CTUN', blocking=False)):
            ctun_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(ctun_data)

'''
def extract_msg_from_bin(bin_path: str) -> pd.DataFrame:
    mav = mavutil.mavlink_connection(bin_path)
    msg_data = []
    try:
        while (msg := mav.recv_match(type='MSG', blocking=False)):
            msg_data.append(msg.to_dict())
    finally:
        mav.close()
    return pd.DataFrame(msg_data)
'''

def extract_gps_date_from_bin(bin_path: str, tz_offset: int = 7) -> pd.Timestamp | None:
    """
    Extracts the first GPS timestamp from a MAVLink .bin file,
    converts it to local time (UTC+7, +8, or +9),
    and returns the datetime (used for folder naming).
    """
    if tz_offset not in [7, 8, 9]:
        raise ValueError("tz_offset must be 7, 8, or 9")

    mav = mavutil.mavlink_connection(bin_path)
    try:
        while (msg := mav.recv_match(type='GPS', blocking=False)):
            d = msg.to_dict()
            if 'GWk' in d and 'GMS' in d:
                gps_epoch = datetime(1980, 1, 6, tzinfo=timezone.utc)
                utc_time = gps_epoch + timedelta(weeks=d['GWk'], milliseconds=d['GMS'])
                local_time = utc_time.astimezone(timezone(timedelta(hours=tz_offset)))
                return local_time  # Only first GPS time is needed
    finally:
        mav.close()
    return None

def downsample_df(df: pd.DataFrame, per_sec) -> pd.DataFrame:
    if "TimeUS" not in df.columns or df.empty:
        return df

    # Convert TimeUS to seconds (integer)
    df = df.copy()
    df["sec"] = (df["TimeUS"] // 1_000_000).astype(int)

    # Keep at most `per_sec` rows per second
    downsampled = (
        df.groupby("sec", group_keys=False)
          .apply(lambda g: g.iloc[:per_sec])
          .reset_index(drop=True)
    )

    # Remove the temporary 'sec' column before returning
    if "sec" in downsampled.columns:
        downsampled.drop(columns=["sec"], inplace=True)

    return downsampled
    



def extract_all_bins_filtered(folder_path, output_folder, downsample_val, dtype, tz):
    written_folders = set()

    extractors = {
        "GPS": extract_gps_from_bin,
        "POS": extract_pos_from_bin,
        "RCOU": extract_rcou_from_bin,
        "BAT": extract_bat_from_bin,
        "CMD": extract_cmd_from_bin,
        "MSG": extract_msg_from_bin,
        "MODE": extract_mode_from_bin,
        "CTUN": extract_ctun_from_bin,
    }

    keep_cols = {
        "GPS": ["mavpackettype", "TimeUS", "Status", "GMS", "GWk", "Spd"],
        "POS": ["mavpackettype", "TimeUS", "Lat", "Lng", "RelHomeAlt"],
        "RCOU": ["mavpackettype", "TimeUS", "C11"],
        "BAT": ["mavpackettype", "Inst", "TimeUS", "Curr"],
        "MSG": ["mavpackettype", "TimeUS", "Mission", "Action"],
        "CMD": ["mavpackettype", "TimeUS", "Prm3"],
        "CTUN": ["mavpackettype", "TimeUS", "ThO"],
    }

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".bin"):
            continue

        bin_path = os.path.join(folder_path, filename)
        all_dfs = []

        sysid_thismav = extract_sysid_thismav(bin_path) or "Unknown"
        dt = extract_gps_date_from_bin(bin_path, tz)
        fold_date = dt.strftime("%Y-%m-%d") if dt else "Unknown_Date"

        date_folder = os.path.join(output_folder, fold_date)
        drone_folder = f"{dtype}-{sysid_thismav}"
        drone_output_folder = os.path.join(date_folder, drone_folder)
        os.makedirs(drone_output_folder, exist_ok=True)
        written_folders.add(drone_output_folder)

        # --- Extract RCOU and POS first ---
        rcou_df = extract_rcou_from_bin(bin_path)
        pos_df = extract_pos_from_bin(bin_path)

        # Clean columns
        if not rcou_df.empty:
            rcou_df = rcou_df[[c for c in keep_cols["RCOU"] if c in rcou_df.columns]]
        if not pos_df.empty:
            pos_df = pos_df[[c for c in keep_cols["POS"] if c in pos_df.columns]]

        # --- Dynamic partial downsample for POS based on C11 ---
        if not rcou_df.empty and not pos_df.empty:
            # Align nearest C11 value to each POS TimeUS
            pos_df = pd.merge_asof(
                pos_df.sort_values("TimeUS"),
                rcou_df[["TimeUS", "C11"]].sort_values("TimeUS"),
                on="TimeUS",
                direction="nearest"
            )

            # Split POS data
            pos_high = pos_df[pos_df["C11"] > 1900].copy()     # keep full rate
            pos_low = pos_df[pos_df["C11"] <= 1900].copy()     # downsampled

            if not pos_low.empty:
                pos_low = downsample_df(pos_low, per_sec=downsample_val)

            pos_df = pd.concat([pos_high, pos_low], ignore_index=True).sort_values("TimeUS")
            pos_df.drop(columns=["C11"], inplace=True)  # remove helper column

        elif not pos_df.empty:
            pos_df = downsample_df(pos_df, per_sec=downsample_val)

        # --- Downsample RCOU only when C11 <= 1900 ---
        if not rcou_df.empty:
            rcou_high = rcou_df[rcou_df["C11"] > 1900].copy()
            rcou_low = rcou_df[rcou_df["C11"] <= 1900].copy()

            if not rcou_low.empty:
                rcou_low = downsample_df(rcou_low, per_sec=downsample_val)

            rcou_df = pd.concat([rcou_high, rcou_low], ignore_index=True).sort_values("TimeUS")

        # --- Handle other messages normally ---
        for label, extractor in extractors.items():
            if label in ["POS", "RCOU"]:
                continue  # already handled

            df = extractor(bin_path)
            if df.empty:
                continue

            cols = keep_cols.get(label, df.columns.tolist())
            df = df[[c for c in cols if c in df.columns]]

            if label == "BAT" and "Inst" in df.columns:
                df0 = df[df["Inst"] == 0].copy()
                df1 = df[df["Inst"] == 1].copy()
                for i, subdf in enumerate([df0, df1], start=1):
                    if not subdf.empty:
                        subdf["mavpackettype"] = f"BAT{i}"
                        subdf = subdf.drop(columns=["Inst"])
                        subdf = downsample_df(subdf, per_sec=downsample_val)
                        all_dfs.append(subdf)

            elif label == "CMD":
                all_dfs.append(df)
            else:
                df = downsample_df(df, per_sec=downsample_val)
                all_dfs.append(df)

        # --- Add POS and RCOU back ---
        if not rcou_df.empty:
            all_dfs.append(rcou_df)
        if not pos_df.empty:
            all_dfs.append(pos_df)

        # --- Merge & save ---
        if all_dfs:
            merged = pd.concat(all_dfs, ignore_index=True)
            base_name = os.path.splitext(filename)[0]
            out_path = os.path.join(
                drone_output_folder,
                f"{base_name} - {dtype}-{sysid_thismav} (DS{downsample_val}).csv"
            )

            print(f"[Sukses memfilter BIN ke CSV] {base_name}.bin -> {out_path}")
            merged.to_csv(out_path, index=False)

    return list(written_folders)
